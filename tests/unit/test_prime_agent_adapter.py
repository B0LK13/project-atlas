"""Contract tests for the pinned Prime Agent RPC adapter (P2-LOCAL-001)."""

from __future__ import annotations

import hashlib
import json
import socket
import threading
from pathlib import Path

import pytest

from project_atlas.orchestration.program.adapters.base import (
    AdapterRequest,
    AdapterUnavailableError,
)
from project_atlas.orchestration.program.adapters.prime_agent import (
    ADAPTER_VERSION,
    PRIME_UPSTREAM_SHA,
    PrimeChildAdmissionBroker,
    PrimeDaemonClient,
    PrimeExecutorAdapter,
    PrimeFrameError,
    PrimeFrameParser,
    _git_identity,
    _prime_failure_class,
    _resume_cursor_for_session,
    _usage_from_session_stats,
    _valid_child_journal_lines,
    _validate_autonomous_limits,
    probe_local_model_endpoint,
)
from project_atlas.orchestration.program.profiles import AdapterKind, AgentProfile


def test_parser_accepts_lf_and_crlf_but_not_unicode_record_separators() -> None:
    parser = PrimeFrameParser(max_frame_bytes=1024)
    value = json.dumps(
        {"type": "response", "id": "1", "data": {"message": "a\u2028b"}},
        ensure_ascii=False,
    )

    assert parser.feed((value + "\r\n").encode())[0]["data"]["message"] == "a\u2028b"
    assert parser.feed(b'{"type":"response","id":"2"}\n')[0]["id"] == "2"


def test_parser_rejects_malformed_and_oversized_records() -> None:
    parser = PrimeFrameParser(max_frame_bytes=8)

    with pytest.raises(PrimeFrameError, match="invalid JSON"):
        parser.feed(b"not-json\n")
    with pytest.raises(PrimeFrameError, match="frame exceeds"):
        parser.feed(b'{"long":true}\n')

    parser = PrimeFrameParser(max_frame_bytes=8)
    with pytest.raises(PrimeFrameError, match="frame exceeds"):
        parser.feed(b'{}\n{"long":t')


def test_prompt_ack_is_not_a_terminal_result() -> None:
    adapter = PrimeExecutorAdapter(executable="prime-agent")
    assert adapter.capabilities.adapter_id == "prime-agent"
    assert adapter.capabilities.supports_resume is False
    assert adapter.capabilities.supports_session_probe is True
    assert adapter.capabilities.accepts_assigned_session is False
    assert adapter.capabilities.version == ADAPTER_VERSION
    assert adapter.upstream_sha == PRIME_UPSTREAM_SHA


def test_command_ids_are_stable_for_reconnect_replay() -> None:
    client = PrimeDaemonClient(Path("/tmp/prime-test.sock"), client_id="atlas-client")
    command = {"type": "attach", "activeSessionId": "session-1"}

    assert client._next_command_id("attach", command) == client._next_command_id(
        "attach", command
    )
    assert client._next_command_id("attach", {**command, "activeSessionId": "session-2"}) != (
        client._next_command_id("attach", command)
    )


def test_usage_keeps_unknown_billing_distinct_from_zero() -> None:
    assert _usage_from_session_stats(None) == (
        {"status": "not-reported-by-public-daemon"},
        None,
    )
    usage, cost = _usage_from_session_stats({"tokens": {"input": 4, "output": 2}, "cost": 0})
    assert usage == {
        "status": "reported",
        "tokens": {"input": 4, "output": 2},
        "client_estimated_cost_usd": 0.0,
        "billing_status": "not-billed-amount",
    }
    assert cost == 0.0


def test_provider_rejection_is_not_classified_as_an_infrastructure_retry() -> None:
    from project_atlas.orchestration.program.models import FailureClass

    assert (
        _prime_failure_class("HTTP 401: API key is unauthorized")
        is FailureClass.QUOTA_OR_CREDENTIAL
    )
    assert (
        _prime_failure_class("daemon socket disappeared")
        is FailureClass.TRANSIENT_INFRASTRUCTURE
    )


def test_child_journal_probe_requires_bound_valid_records() -> None:
    line = json.dumps(
        {
            "event": "reserved",
            "mission_id": "m",
            "task_id": "t",
            "attempt_id": "a",
            "record": {"phase": "reserved"},
        }
    )
    assert _valid_child_journal_lines([line], mission_id="m", task_id="t", attempt_id="a")
    assert not _valid_child_journal_lines(
        [line], mission_id="other", task_id="t", attempt_id="a"
    )
    assert not _valid_child_journal_lines(
        ["not-json"], mission_id="m", task_id="t", attempt_id="a"
    )


def test_child_admission_broker_binds_and_accounts_native_children(tmp_path: Path) -> None:
    broker = PrimeChildAdmissionBroker(
        tmp_path / "child.sock",
        mission_id="mission-1",
        task_id="task-1",
        attempt_id="attempt-1",
        parent_session_id="session-1",
        max_children=1,
        role="prime-agent",
        scope_hash="b" * 64,
        max_child_seconds=10,
        max_child_tokens=100,
        max_budget_seconds=10,
        candidate_sha="c" * 40,
        tree_sha="d" * 40,
        workspace_identity="/mission/workspace",
    )
    broker.start()

    def call(payload: dict[str, object]) -> dict[str, object]:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(2)
        connection.connect(str(broker.socket_path))
        with connection:
            connection.sendall((json.dumps(payload) + "\n").encode())
            return json.loads(connection.makefile("rb").readline())

    base = {
        "protocol": "atlas-prime-child-admission",
        "version": 1,
        "mission_id": "mission-1",
        "task_id": "task-1",
        "attempt_id": "attempt-1",
        "parent_session_id": "session-1",
        "role": "prime-agent",
        "scope_hash": "b" * 64,
        "max_child_seconds": 10,
        "max_child_tokens": 100,
    }
    try:
        reserved = call({**base, "phase": "reserve", "name": "review", "prompt_sha256": "a" * 64})
        assert reserved["ok"] is True
        admission_id = reserved["admission_id"]
        assert call(
            {**base, "phase": "reserve", "name": "second", "prompt_sha256": "b" * 64}
        )["ok"] is False
        assert call({
            **base,
            "phase": "commit",
            "admission_id": admission_id,
            "child_id": "sub-1",
            "session_dir": "/mission/sub-1",
        })["ok"] is True
        assert call(
            {**base, "phase": "release", "admission_id": admission_id, "status": "done"}
        )["ok"] is True
        assert call(
            {**base, "phase": "reserve", "name": "third", "prompt_sha256": "c" * 64}
        )["ok"] is False
        assert broker.records == [
            {
                "admission_id": admission_id,
                "name": "review",
                "prompt_sha256": "a" * 64,
                "phase": "released",
                "child_id": "sub-1",
                "session_dir": "/mission/sub-1",
                "status": "done",
                "role": "prime-agent",
                "scope_hash": "b" * 64,
                "budget_reserved": {"seconds": 10, "tokens": 100},
            }
        ]
        journal = [
            json.loads(line)
            for line in broker.journal_path.read_text(encoding="utf-8").splitlines()
        ]
        assert [entry["event"] for entry in journal] == [
            "reserved",
            "committed",
            "released",
        ]
        assert all(entry["attempt_id"] == "attempt-1" for entry in journal)
        assert all(entry["candidate_sha"] == "c" * 40 for entry in journal)
        assert all(entry["tree_sha"] == "d" * 40 for entry in journal)
        assert all(entry["workspace_identity"] == "/mission/workspace" for entry in journal)
    finally:
        broker.close()


def test_local_model_probe_is_catalog_only_and_loopback_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return b'{"data":[{"id":"qwen"},{"id":"llama"}]}'

    monkeypatch.setattr(
        "project_atlas.orchestration.program.adapters.prime_agent.urlopen",
        lambda url, timeout: Response(),
    )
    assert probe_local_model_endpoint("http://127.0.0.1:11434") == {
        "endpoint": "http://127.0.0.1:11434",
        "reachable": True,
        "models": ["llama", "qwen"],
    }
    with pytest.raises(ValueError, match="loopback"):
        probe_local_model_endpoint("https://models.example.invalid")


def test_preflight_requires_an_explicit_external_isolation_route(tmp_path: Path) -> None:
    profile = AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        adapter_options={"executable": str(tmp_path / "prime-agent")},
    )
    adapter = PrimeExecutorAdapter(str(tmp_path / "prime-agent"))

    with pytest.raises(AdapterUnavailableError, match="external isolation"):
        adapter.preflight(profile)


def test_preflight_requires_a_source_bound_runtime_manifest(tmp_path: Path) -> None:
    fake = tmp_path / "prime-agent"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    profile = AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        adapter_options={"sandbox_argv": ["/bin/true"]},
    )

    with pytest.raises(AdapterUnavailableError, match="runtime_manifest"):
        PrimeExecutorAdapter(str(fake)).preflight(profile)


def test_preflight_rejects_a_non_isolating_existing_wrapper(tmp_path: Path) -> None:
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
            }
        ),
        encoding="utf-8",
    )
    profile = AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        credential="NOT_APPLICABLE",
        adapter_options={
            "sandbox_argv": ["/bin/true"],
            "runtime_manifest": str(manifest),
        },
    )

    with pytest.raises(AdapterUnavailableError, match="Bubblewrap"):
        PrimeExecutorAdapter(str(fake)).preflight(profile)


def test_preflight_rejects_a_broad_host_mount(tmp_path: Path) -> None:
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
            }
        ),
        encoding="utf-8",
    )
    profile = AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        credential="NOT_APPLICABLE",
        adapter_options={
            "sandbox_argv": [
                "/usr/bin/bwrap",
                "--die-with-parent",
                "--new-session",
                "--unshare-all",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--tmpfs",
                "/tmp",
                "--ro-bind",
                "/",
                "/host",
                "--chdir",
                str(tmp_path),
            ],
            "runtime_manifest": str(manifest),
        },
    )

    with pytest.raises(AdapterUnavailableError, match="outside the approved mission scope"):
        PrimeExecutorAdapter(str(fake)).preflight(profile)


def test_preflight_rejects_a_manifest_bound_to_another_executable(tmp_path: Path) -> None:
    fake = tmp_path / "prime-agent"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "upstream_sha": PRIME_UPSTREAM_SHA,
                "source_commit_verified": True,
                "executable": {"path": "/bin/false", "sha256": "0" * 64},
            }
        ),
        encoding="utf-8",
    )
    profile = AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        adapter_options={
            "sandbox_argv": ["/bin/true"],
            "runtime_manifest": str(manifest),
        },
    )

    with pytest.raises(AdapterUnavailableError, match="executable identity"):
        PrimeExecutorAdapter(str(fake)).preflight(profile)


def test_prime_autonomous_limits_must_be_finite_and_within_atlas_deadline() -> None:
    with pytest.raises(AdapterUnavailableError, match="finite"):
        _validate_autonomous_limits({"maxTokens": 1000}, 60)
    with pytest.raises(AdapterUnavailableError, match="exceeds"):
        _validate_autonomous_limits(
            {
                "maxContinuations": 2,
                "maxTurns": 4,
                "maxTokens": 1000,
                "timeoutMs": 60_001,
            },
            60,
        )
    _validate_autonomous_limits(
        {
            "maxContinuations": 2,
            "maxTurns": 4,
            "maxTokens": 1000,
            "timeoutMs": 60_000,
            "subagentKeepAliveMs": 10_000,
        },
        60,
    )


def test_preflight_rejects_unadmitted_recursive_children(tmp_path: Path) -> None:
    fake = tmp_path / "prime-agent"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    profile = AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        adapter_options={
            "sandbox_argv": ["/bin/true"],
            "allow_children": True,
        },
    )

    with pytest.raises(AdapterUnavailableError, match="host-side admission"):
        PrimeExecutorAdapter(str(fake)).preflight(profile)


def test_client_owned_recovery_requires_a_noncredential_profile(tmp_path: Path) -> None:
    fake = tmp_path / "prime-agent"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    profile = AgentProfile(
        profile_id="prime-owned",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        adapter_options={
            "sandbox_argv": ["/bin/true"],
            "daemon_lifecycle": "client_owned",
        },
    )

    with pytest.raises(AdapterUnavailableError, match="credential env"):
        PrimeExecutorAdapter(str(fake)).preflight(profile)


def test_run_requires_agent_end_after_prompt_ack(tmp_path: Path) -> None:
    fake = tmp_path / "prime-agent"
    ack = '{"id":"k","type":"response","command":"prompt","success":true}'
    end = '{"type":"agent_end","data":{"sessionId":"prime-s-1","text":"changed files"}}'
    fake.write_text(
        "#!/bin/sh\n"
        "read command\n"
        f"printf '%s\\n' '{ack}'\n"
        f"printf '%s\\n' '{end}'\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    evidence = tmp_path / "evidence"
    profile = AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        adapter_options={"executable": str(fake)},
    )
    request = AdapterRequest(
        program_id="program",
        task_id="task",
        attempt_id="attempt",
        attempt_number=1,
        idempotency_key="k",
        instruction="make the change",
        workspace=workspace,
        profile=profile,
        session_id=None,
        resume_session_id=None,
        timeout_seconds=5,
        evidence_dir=evidence,
    )

    outcome = PrimeExecutorAdapter(str(fake)).run(request)

    assert outcome.confidence.value == "CONFIRMED"
    assert outcome.terminal_state == "completed"
    assert outcome.session_id == "prime-s-1"
    assert outcome.reported == "changed files"
    first_frame = json.loads((evidence / "attempt.prime-rpc.jsonl").read_text().splitlines()[0])
    assert first_frame["type"] == "response"


def test_daemon_client_uses_public_v7_envelope_and_resident_session(tmp_path: Path) -> None:
    socket_path = tmp_path / "prime-daemon.sock"
    ready = threading.Event()
    received: list[dict[str, object]] = []

    def serve() -> None:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(socket_path))
        server.listen(1)
        ready.set()
        connection, _ = server.accept()
        with connection, connection.makefile("rb") as reader:
            connection.sendall(
                b'{"type":"daemon_hello","protocol":{"name":"prime-agent.daemon","version":7},"serverCapabilities":["attach_snapshot"]}\n'
            )
            for raw in reader:
                command = json.loads(raw)
                received.append(command)
                body = command["command"]
                if body["type"] == "create":
                    data = {"activeSessionId": "active-1"}
                elif body["type"] == "prompt_and_wait":
                    data = None
                elif body["type"] == "get_session_stats":
                    data = {"tokens": {"input": 12, "output": 3}, "cost": 0.001}
                else:
                    data = {"text": "daemon result"}
                response = {
                    "type": "response",
                    "id": command["id"],
                    "command": body["type"],
                    "success": True,
                }
                if data is not None:
                    response["data"] = data
                connection.sendall((json.dumps(response) + "\n").encode())
        server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    client = PrimeDaemonClient(socket_path, client_id="atlas-client-1")
    client.connect()
    assert client.server_capabilities == ("attach_snapshot",)
    active_session_id = client.create_resident(
        session_path=tmp_path / "session.jsonl",
        cwd=tmp_path,
        session_dir=tmp_path / "sessions",
        autonomous={
            "enabled": True,
            "maxContinuations": 2,
            "maxTurns": 4,
            "maxTokens": 1000,
            "timeoutMs": 60_000,
        },
    )
    client.set_rlm_max_depth(active_session_id, 0)
    client.prompt_and_wait(active_session_id, "do work", admission_id="atlas-client-1")
    assert client.last_assistant_text(active_session_id) == "daemon result"
    assert client.session_stats(active_session_id) == {
        "tokens": {"input": 12, "output": 3},
        "cost": 0.001,
    }
    client.close()
    thread.join(timeout=2)

    assert received[0]["type"] == "command"
    assert received[0]["protocol"] == {
        "name": "prime-agent.daemon",
        "version": 7,
    }
    assert received[0]["clientId"] == "atlas-client-1"
    assert received[0]["command"]["lifecycle"] == "resident"
    assert received[0]["command"]["config"]["autonomous"]["maxTokens"] == 1000
    assert len(received) == 5
    assert any(
        item["command"]["type"] == "prompt_and_wait"
        and item["command"]["admissionId"] == "atlas-client-1"
        for item in received
    )
    assert any(
        item["command"]["type"] == "set_rlm_max_depth"
        and item["command"]["maxDepth"] == 0
        for item in received
    )


def test_daemon_client_preserves_attach_cursor_and_ignores_stale_events(tmp_path: Path) -> None:
    socket_path = tmp_path / "prime-daemon.sock"
    ready = threading.Event()
    received: list[dict[str, object]] = []

    def serve() -> None:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(socket_path))
        server.listen(1)
        ready.set()
        connection, _ = server.accept()
        with connection, connection.makefile("rb") as reader:
            connection.sendall(
                b'{"type":"daemon_hello","protocol":{"name":"prime-agent.daemon","version":7},"serverCapabilities":["attach_snapshot","event_sequence","owned_session_recovery_context"]}\n'
            )
            for raw in reader:
                command = json.loads(raw)
                received.append(command)
                body = command["command"]
                if body["type"] == "attach":
                    connection.sendall(
                        b'{"type":"event","activeSessionId":"active-1","sequence":3,"cursor":{"generation":"g1","sequence":3},"event":{"type":"session_event"}}\n'
                    )
                    connection.sendall(
                        b'{"type":"event","activeSessionId":"active-1","sequence":5,"cursor":{"generation":"g1","sequence":5},"event":{"type":"session_event"}}\n'
                    )
                    data = {
                        "activeSessionId": "active-1",
                        "snapshot": {
                            "activeSessionId": "active-1",
                            "lastEventSequence": 5,
                            "lastEventCursor": {"generation": "g1", "sequence": 5},
                        },
                        "replay": {"status": "complete"},
                        "lastEventSequence": 5,
                        "lastEventCursor": {"generation": "g1", "sequence": 5},
                    }
                else:
                    data = None
                response = {
                    "type": "response",
                    "id": command["id"],
                    "command": body["type"],
                    "success": True,
                }
                if data is not None:
                    response["data"] = data
                connection.sendall((json.dumps(response) + "\n").encode())
        server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    client = PrimeDaemonClient(socket_path, client_id="atlas-client-2")
    client.connect()
    client.attach("active-1")
    assert client.last_event_cursor == {"generation": "g1", "sequence": 5}
    assert client.last_event_sequence == 5
    assert client.snapshot == {
        "activeSessionId": "active-1",
        "lastEventSequence": 5,
        "lastEventCursor": {"generation": "g1", "sequence": 5},
    }
    attach = next(item for item in received if item["command"]["type"] == "attach")
    assert attach["command"]["capabilities"] == ["attach_snapshot", "event_sequence"]
    assert "resumeCursor" not in attach["command"]

    # A reconnect-style attach using the saved cursor must advertise it to Prime.
    client.resume_cursor = {"generation": "g1", "sequence": 5}
    client.attach(
        "active-1",
        recovery_config={"cwd": str(tmp_path)},
        launch_env={},
    )
    client.close()
    thread.join(timeout=2)
    assert received[-1]["command"]["resumeCursor"] == {
        "activeSessionId": "active-1",
        "generation": "g1",
        "sequence": 5,
    }
    assert received[-1]["command"]["capabilities"] == [
        "attach_snapshot",
        "event_sequence",
        "owned_session_recovery_context",
    ]
    assert received[-1]["command"]["recoveryConfig"] == {"cwd": str(tmp_path)}
    assert received[-1]["command"]["launchEnv"] == {}


def test_resume_cursor_is_loaded_only_for_the_requested_session(tmp_path: Path) -> None:
    (tmp_path / "old.prime-daemon.json").write_text(
        json.dumps(
            {
                "prime_active_session_id": "other",
                "last_event_cursor": {"generation": "old", "sequence": 99},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "current.prime-daemon.json").write_text(
        json.dumps(
            {
                "prime_active_session_id": "active-1",
                "last_event_cursor": {"generation": "g1", "sequence": 7},
            }
        ),
        encoding="utf-8",
    )

    assert _resume_cursor_for_session(tmp_path, "active-1") == {
        "generation": "g1",
        "sequence": 7,
    }
    assert _resume_cursor_for_session(tmp_path, "missing") is None


def test_git_identity_is_read_only_and_safe_for_non_git_workspaces(tmp_path: Path) -> None:
    assert _git_identity(tmp_path) == (None, None)
