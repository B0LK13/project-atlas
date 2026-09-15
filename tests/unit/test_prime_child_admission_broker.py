"""Hardening contract tests for the Prime child-admission broker.

Each test runs a live ``PrimeChildAdmissionBroker`` and speaks to it over a
real AF_UNIX socket, one JSONL request per connection, mirroring the pinned
Prime compatibility patch's wire behavior.
"""

from __future__ import annotations

import hashlib
import json
import socket
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.program.adapters.base import AdapterUnavailableError
from project_atlas.orchestration.program.adapters.prime_agent import (
    CHILD_ADMISSION_PATCH_ID,
    CHILD_ADMISSION_PATCH_SHA256,
    PRIME_UPSTREAM_SHA,
    PrimeChildAdmissionBroker,
    PrimeExecutorAdapter,
)
from project_atlas.orchestration.program.profiles import AdapterKind, AgentProfile

_PROTOCOL = "atlas-prime-child-admission"


def _start_broker(
    tmp_path: Path,
    *,
    max_children: int = 1,
    max_child_seconds: int = 10,
    max_budget_seconds: int = 30,
    child_models: list[str] | None = None,
    max_child_depth: int = 1,
    parent_session_id: str = "session-1",
    cancel_requested: Any = None,
) -> PrimeChildAdmissionBroker:
    broker = PrimeChildAdmissionBroker(
        tmp_path / "child.sock",
        mission_id="mission-1",
        task_id="task-1",
        attempt_id="attempt-1",
        parent_session_id=parent_session_id,
        max_children=max_children,
        role="prime-agent",
        scope_hash="b" * 64,
        max_child_seconds=max_child_seconds,
        max_child_tokens=100,
        max_budget_seconds=max_budget_seconds,
        child_models=["fixture-model"] if child_models is None else child_models,
        max_child_depth=max_child_depth,
        cancel_requested=cancel_requested,
    )
    broker.start()
    return broker


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "protocol": _PROTOCOL,
        "version": 1,
        "phase": "reserve",
        "mission_id": "mission-1",
        "task_id": "task-1",
        "attempt_id": "attempt-1",
        "parent_session_id": "session-1",
        "role": "prime-agent",
        "scope_hash": "b" * 64,
        "name": "review",
        "prompt_sha256": "a" * 64,
        "max_child_seconds": 10,
        "max_child_tokens": 100,
        "model": "fixture-model",
        "depth": 0,
    }
    payload.update(overrides)
    return payload


def _call(broker: PrimeChildAdmissionBroker, payload: dict[str, Any]) -> dict[str, Any]:
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(2)
    connection.connect(str(broker.socket_path))
    with connection:
        connection.sendall((json.dumps(payload) + "\n").encode())
        return json.loads(connection.makefile("rb").readline())


def _journal_events(broker: PrimeChildAdmissionBroker) -> list[str]:
    return [
        json.loads(line)["event"]
        for line in broker.journal_path.read_text(encoding="utf-8").splitlines()
    ]


def _reserve(broker: PrimeChildAdmissionBroker, **overrides: Any) -> dict[str, Any]:
    return _call(broker, _payload(**overrides))


def _commit(
    broker: PrimeChildAdmissionBroker,
    admission_id: str,
    fencing_token: int,
    child_id: str = "sub-1",
    **overrides: Any,
) -> dict[str, Any]:
    return _call(
        broker,
        _payload(
            phase="commit",
            admission_id=admission_id,
            child_id=child_id,
            session_dir="/mission/sub-1",
            fencing_token=fencing_token,
            **overrides,
        ),
    )


def _release(
    broker: PrimeChildAdmissionBroker,
    admission_id: str,
    fencing_token: int,
    status: str = "done",
    **overrides: Any,
) -> dict[str, Any]:
    return _call(
        broker,
        _payload(
            phase="release",
            admission_id=admission_id,
            status=status,
            fencing_token=fencing_token,
            **overrides,
        ),
    )


def test_broker_constructor_requires_model_allowlist_and_positive_depth(
    tmp_path: Path,
) -> None:
    base = {
        "socket_path": tmp_path / "child.sock",
        "mission_id": "mission-1",
        "task_id": "task-1",
        "attempt_id": "attempt-1",
        "parent_session_id": "session-1",
        "max_children": 1,
        "role": "prime-agent",
        "scope_hash": "b" * 64,
        "max_child_seconds": 10,
        "max_child_tokens": 100,
        "max_budget_seconds": 30,
    }
    for bad_models in ([], ["  "], ["ok", ""]):
        with pytest.raises(ValueError, match="child_models"):
            PrimeChildAdmissionBroker(**base, child_models=bad_models)
    for bad_depth in (0, -1, True):
        with pytest.raises(ValueError, match="max_child_depth"):
            PrimeChildAdmissionBroker(
                **base, child_models=["fixture-model"], max_child_depth=bad_depth
            )


def test_broker_denies_model_and_depth_violations_before_any_effects(tmp_path: Path) -> None:
    broker = _start_broker(tmp_path, max_budget_seconds=10)
    try:
        # A single denied reserve must not consume the only budget unit: the
        # follow-up valid reserve must still succeed (token 1, one record).
        denied_model = _reserve(broker, model="unlisted-model")
        assert denied_model["ok"] is False
        assert denied_model["denial"] == "MODEL_REFUSAL"
        missing_model_payload = _payload()
        del missing_model_payload["model"]
        assert _call(broker, missing_model_payload)["denial"] == "MODEL_REFUSAL"
        non_string_model = _reserve(broker, model=7)
        assert non_string_model["denial"] == "MODEL_REFUSAL"
        assert _reserve(broker, depth=1)["denial"] == "RECURSION_REFUSAL"
        assert _reserve(broker, depth=True)["denial"] == "RECURSION_REFUSAL"
        assert _reserve(broker, depth="0")["denial"] == "RECURSION_REFUSAL"
        missing_depth_payload = _payload()
        del missing_depth_payload["depth"]
        assert _call(broker, missing_depth_payload)["denial"] == "RECURSION_REFUSAL"
        assert broker.records == []
        assert _journal_events(broker) == ["denied"] * 7
        admitted = _reserve(broker)
        assert admitted["ok"] is True
        assert admitted["fencing_token"] == 1
        assert len(broker.records) == 1
    finally:
        broker.close()


def test_broker_admits_depths_below_the_configured_recursion_cap(tmp_path: Path) -> None:
    broker = _start_broker(
        tmp_path, max_children=2, max_child_depth=2, max_budget_seconds=30
    )
    try:
        surface = _reserve(broker, depth=0, name="surface", prompt_sha256="a" * 64)
        nested = _reserve(broker, depth=1, name="nested", prompt_sha256="b" * 64)
        assert surface["ok"] is True
        assert nested["ok"] is True
        assert surface["fencing_token"] == 1
        assert nested["fencing_token"] == 2
        assert nested["max_depth"] == 2
        too_deep = _reserve(broker, depth=2, name="too-deep", prompt_sha256="c" * 64)
        assert too_deep["ok"] is False
        assert too_deep["denial"] == "RECURSION_REFUSAL"
        assert _journal_events(broker) == ["reserved", "reserved", "denied"]
    finally:
        broker.close()


def test_broker_denies_fencing_mismatch_on_commit_and_release_without_effects(
    tmp_path: Path,
) -> None:
    broker = _start_broker(tmp_path)
    try:
        reserved = _reserve(broker)
        assert reserved["ok"] is True
        admission_id = reserved["admission_id"]
        token = reserved["fencing_token"]
        wrong_commit = _commit(broker, admission_id, token + 1)
        assert wrong_commit["ok"] is False
        assert wrong_commit["denial"] == "FENCING_REFUSED"
        missing_token_commit = _commit(broker, admission_id, "not-a-token")
        assert missing_token_commit["denial"] == "FENCING_REFUSED"
        # The record is untouched and still reservable under the right token.
        assert broker.records[0]["phase"] == "reserved"
        assert _journal_events(broker) == ["reserved", "denied", "denied"]
        assert _commit(broker, admission_id, token)["ok"] is True
        wrong_release = _release(broker, admission_id, token + 1)
        assert wrong_release["ok"] is False
        assert wrong_release["denial"] == "FENCING_REFUSED"
        missing_token_release = _release(broker, admission_id, 0)
        assert missing_token_release["denial"] == "FENCING_REFUSED"
        assert broker.records[0]["phase"] == "committed"
        assert _release(broker, admission_id, token)["ok"] is True
        assert broker.records[0]["phase"] == "released"
    finally:
        broker.close()


def test_broker_commit_and_release_are_idempotent_retries(tmp_path: Path) -> None:
    broker = _start_broker(tmp_path)
    try:
        reserved = _reserve(broker)
        admission_id = reserved["admission_id"]
        token = reserved["fencing_token"]
        assert _commit(broker, admission_id, token)["ok"] is True
        retry = _commit(broker, admission_id, token)
        assert retry["ok"] is True
        conflict = _commit(broker, admission_id, token, child_id="sub-2")
        assert conflict["ok"] is False
        assert conflict["denial"] == "STATE_REFUSAL"
        assert _release(broker, admission_id, token, status="done")["ok"] is True
        assert _release(broker, admission_id, token, status="done")["ok"] is True
        status_conflict = _release(broker, admission_id, token, status="error")
        assert status_conflict["ok"] is False
        assert status_conflict["denial"] == "STATE_REFUSAL"
        assert _journal_events(broker) == [
            "reserved",
            "committed",
            "denied",
            "released",
            "denied",
        ]
        assert len(broker.records) == 1
        assert broker.records[0]["phase"] == "released"
        assert broker.records[0]["child_id"] == "sub-1"
    finally:
        broker.close()


def test_broker_deduplicates_active_reserve_and_spends_slot_budget_once(
    tmp_path: Path,
) -> None:
    broker = _start_broker(tmp_path, max_budget_seconds=10)
    try:
        first = _reserve(broker)
        second = _reserve(broker)
        assert first["ok"] is True
        assert second["ok"] is True
        assert second["admission_id"] == first["admission_id"]
        assert second["fencing_token"] == first["fencing_token"]
        # Only one slot was consumed: a different child is refused.
        other = _reserve(broker, name="other", prompt_sha256="b" * 64)
        assert other["ok"] is False
        assert other["denial"] == "CAPACITY_REFUSAL"
        assert _journal_events(broker) == ["reserved", "reserve_retry", "denied"]
        assert _commit(broker, first["admission_id"], first["fencing_token"])["ok"] is True
        assert _release(broker, first["admission_id"], first["fencing_token"])["ok"] is True
        assert len(broker.records) == 1
        assert broker.records[0]["phase"] == "released"
        assert broker.records[0]["child_id"] == "sub-1"
        assert _journal_events(broker) == [
            "reserved",
            "reserve_retry",
            "denied",
            "committed",
            "released",
        ]
    finally:
        broker.close()


def test_broker_recovers_uncertain_reserve_outcome_via_dedup(tmp_path: Path) -> None:
    broker = _start_broker(tmp_path, max_budget_seconds=10)
    payload = _payload()
    try:
        # The reserve reaches the broker, but the client "loses" the response.
        lost = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        lost.settimeout(2)
        lost.connect(str(broker.socket_path))
        lost.sendall((json.dumps(payload) + "\n").encode())
        time.sleep(0.5)
        lost.close()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and _journal_events(broker) != ["reserved"]:
            time.sleep(0.05)
        assert _journal_events(broker) == ["reserved"]
        record = json.loads(
            broker.journal_path.read_text(encoding="utf-8").splitlines()[0]
        )["record"]
        # The client re-sends the identical reserve and must observe the same
        # identity without double-spending the slot or the budget.
        retry = _call(broker, payload)
        assert retry["ok"] is True
        assert retry["admission_id"] == record["admission_id"]
        assert retry["fencing_token"] == record["fencing_token"]
        assert _journal_events(broker) == ["reserved", "reserve_retry"]
        assert _commit(broker, record["admission_id"], record["fencing_token"])["ok"] is True
        assert _release(broker, record["admission_id"], record["fencing_token"])["ok"] is True
        assert _journal_events(broker) == [
            "reserved",
            "reserve_retry",
            "committed",
            "released",
        ]
        # Budget was spent exactly once: a fresh child is refused by budget
        # even though the slot is free again.
        follow_up = _reserve(broker, name="follow-up", prompt_sha256="b" * 64)
        assert follow_up["ok"] is False
        assert follow_up["denial"] == "BUDGET_REFUSAL"
        assert len(broker.records) == 1
    finally:
        broker.close()


def test_broker_parent_stop_denies_reserve_and_journals_it(tmp_path: Path) -> None:
    stopped = threading.Event()
    stopped.set()
    broker = _start_broker(tmp_path, cancel_requested=stopped.is_set)
    try:
        denied = _reserve(broker)
        assert denied["ok"] is False
        assert denied["denial"] == "CANCELLED"
        assert broker.records == []
        assert _journal_events(broker) == ["denied"]
    finally:
        broker.close()


def test_broker_adopts_first_seen_parent_binding_and_denies_mismatch(
    tmp_path: Path,
) -> None:
    broker = _start_broker(tmp_path, parent_session_id="")
    try:
        unbound_payload = _payload()
        del unbound_payload["parent_session_id"]
        assert _call(broker, unbound_payload)["denial"] == "BINDING_REFUSAL"
        adopted = _reserve(broker, parent_session_id="adopted-session")
        assert adopted["ok"] is True
        assert broker.parent_session_id == "adopted-session"
        assert _journal_events(broker) == ["denied", "parent_bound", "reserved"]
        hijack = _reserve(broker, parent_session_id="other-session")
        assert hijack["ok"] is False
        assert hijack["denial"] == "BINDING_REFUSAL"
        # The adopted binding still answers commit/release for the admission.
        assert _commit(
            broker,
            adopted["admission_id"],
            adopted["fencing_token"],
            parent_session_id="adopted-session",
        )["ok"] is True
        assert _release(
            broker,
            adopted["admission_id"],
            adopted["fencing_token"],
            parent_session_id="adopted-session",
        )["ok"] is True
        assert _journal_events(broker) == [
            "denied",
            "parent_bound",
            "reserved",
            "denied",
            "committed",
            "released",
        ]
    finally:
        broker.close()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("parent_session_id", "other-session"),
        ("role", "rogue-role"),
        ("scope_hash", "c" * 64),
        ("mission_id", "other-mission"),
    ],
)
def test_broker_denies_binding_mismatch_after_parent_bound(
    tmp_path: Path, field: str, value: str
) -> None:
    broker = _start_broker(tmp_path)
    try:
        denied = _reserve(broker, **{field: value})
        assert denied["ok"] is False
        assert denied["denial"] == "BINDING_REFUSAL"
        assert broker.records == []
        assert _journal_events(broker) == ["denied"]
    finally:
        broker.close()


def test_broker_cumulative_budget_is_never_refunded(tmp_path: Path) -> None:
    broker = _start_broker(tmp_path, max_budget_seconds=10)
    try:
        first = _reserve(broker)
        assert first["ok"] is True
        assert _commit(broker, first["admission_id"], first["fencing_token"])["ok"] is True
        assert _release(broker, first["admission_id"], first["fencing_token"])["ok"] is True
        # The slot is free again, but the never-refunded cumulative budget
        # refuses a second child.
        second = _reserve(broker, name="second", prompt_sha256="b" * 64)
        assert second["ok"] is False
        assert second["denial"] == "BUDGET_REFUSAL"
        assert len(broker.records) == 1
        assert _journal_events(broker) == ["reserved", "committed", "released", "denied"]
    finally:
        broker.close()


def test_broker_denies_second_reserve_immediately_while_single_slot_held(
    tmp_path: Path,
) -> None:
    broker = _start_broker(tmp_path)
    try:
        held = _reserve(broker)
        assert held["ok"] is True
        started = time.monotonic()
        denied = _reserve(broker, name="blocked", prompt_sha256="b" * 64)
        elapsed = time.monotonic() - started
        assert denied["ok"] is False
        assert denied["denial"] == "CAPACITY_REFUSAL"
        assert elapsed < 2.0
        assert _release(broker, held["admission_id"], held["fencing_token"])["ok"] is True
    finally:
        broker.close()


def test_broker_concurrent_reserves_admit_exactly_one_child_for_one_slot(
    tmp_path: Path,
) -> None:
    broker = _start_broker(tmp_path, max_budget_seconds=20)
    barrier = threading.Barrier(2)
    results: dict[str, dict[str, Any]] = {}
    errors: dict[str, BaseException] = {}

    def contender(name: str, prompt_sha256: str) -> None:
        try:
            barrier.wait(timeout=2)
            results[name] = _reserve(
                broker, name=name, prompt_sha256=prompt_sha256
            )
        except BaseException as exc:  # pragma: no cover - assertion aid
            errors[name] = exc

    threads = [
        threading.Thread(target=contender, args=("first", "a" * 64)),
        threading.Thread(target=contender, args=("second", "b" * 64)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    assert sorted(result["ok"] for result in results.values()) == [False, True]
    assert sum(1 for result in results.values() if result["ok"]) == 1
    admitted = next(result for result in results.values() if result["ok"])
    assert admitted["fencing_token"] == 1
    assert len(broker.records) == 1
    events = _journal_events(broker)
    assert sorted(events) == ["denied", "reserved"]
    _commit(broker, admitted["admission_id"], admitted["fencing_token"])
    _release(broker, admitted["admission_id"], admitted["fencing_token"])


def test_broker_denies_malformed_protocol_and_phase(tmp_path: Path) -> None:
    broker = _start_broker(tmp_path)
    try:
        wrong_protocol = _reserve(broker, protocol="something-else")
        assert wrong_protocol["ok"] is False
        assert wrong_protocol["denial"] == "PROTOCOL_REFUSAL"
        wrong_version = _reserve(broker, version=2)
        assert wrong_version["denial"] == "PROTOCOL_REFUSAL"
        unknown_phase = _reserve(broker, phase="renegotiate")
        assert unknown_phase["denial"] == "PHASE_REFUSAL"
        assert broker.records == []
        assert _journal_events(broker) == ["denied", "denied", "denied"]
    finally:
        broker.close()


def _child_admission_profile(
    tmp_path: Path, child_admission: dict[str, Any]
) -> AgentProfile:
    fake = tmp_path / "prime-agent"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "upstream_sha": PRIME_UPSTREAM_SHA,
                "source_commit_verified": True,
                "executable": {
                    "path": str(fake.resolve()),
                    "sha256": hashlib.sha256(fake.read_bytes()).hexdigest(),
                },
                "compatibility_patches": [
                    {
                        "id": CHILD_ADMISSION_PATCH_ID,
                        "sha256": CHILD_ADMISSION_PATCH_SHA256,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        adapter_options={
            "executable": str(fake),
            "sandbox_argv": ["/bin/true"],
            "allow_children": True,
            "runtime_manifest": str(manifest),
            "child_admission": child_admission,
        },
    )


def _admitted_child_options(**overrides: Any) -> dict[str, Any]:
    options: dict[str, Any] = {
        "patch_id": CHILD_ADMISSION_PATCH_ID,
        "max_children": 1,
        "max_child_seconds": 10,
        "max_budget_seconds": 10,
        "child_models": ["fixture-model"],
    }
    options.update(overrides)
    return options


def test_preflight_requires_child_models_allowlist_when_children_admitted(
    tmp_path: Path,
) -> None:
    profile = _child_admission_profile(
        tmp_path,
        {
            "patch_id": CHILD_ADMISSION_PATCH_ID,
            "max_children": 1,
            "max_child_seconds": 10,
            "max_budget_seconds": 10,
        },
    )
    adapter = PrimeExecutorAdapter(
        str(tmp_path / "prime-agent"), daemon_socket=tmp_path / "prime.sock"
    )
    with pytest.raises(AdapterUnavailableError, match="child_models"):
        adapter.preflight(profile)


def test_preflight_rejects_invalid_child_depth_when_children_admitted(
    tmp_path: Path,
) -> None:
    for bad_depth in (0, -1, True, "1"):
        profile = _child_admission_profile(
            tmp_path, _admitted_child_options(max_child_depth=bad_depth)
        )
        adapter = PrimeExecutorAdapter(
            str(tmp_path / "prime-agent"), daemon_socket=tmp_path / "prime.sock"
        )
        with pytest.raises(AdapterUnavailableError, match="max_child_depth"):
            adapter.preflight(profile)


def test_preflight_accepts_admitted_child_options_and_moves_past_the_gate(
    tmp_path: Path,
) -> None:
    profile = _child_admission_profile(
        tmp_path, _admitted_child_options(max_child_depth=2)
    )
    adapter = PrimeExecutorAdapter(
        str(tmp_path / "prime-agent"), daemon_socket=tmp_path / "prime.sock"
    )
    # The child-admission gate passes; the next refusal is the isolation
    # wrapper, proving model allowlist and depth were accepted.
    with pytest.raises(AdapterUnavailableError, match="Bubblewrap"):
        adapter.preflight(profile)
