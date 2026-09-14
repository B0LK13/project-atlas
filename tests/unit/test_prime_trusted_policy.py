"""Trusted-policy binding tests for the Prime adapter (PRIME-LOCAL-001).

The runbook binds ``adapter_options.policy_path`` to a policy file that must
live OUTSIDE the worker-writable workspace; its sha256 is recorded as
``policy_hash`` in the attempt metadata. Absent configuration stays absent:
``policy_hash`` is ``None``, honest absence rather than an invented digest.

Protocol note: ``RuntimeAdapter.preflight`` receives only the profile, so the
workspace-containment half cannot run there; it is enforced at dispatch, the
first point that knows the resolved mission workspace. The tests below say so
where they bind the containment refusal to the resident run rather than to
``preflight`` itself.
"""

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
    PRIME_UPSTREAM_SHA,
    PrimeExecutorAdapter,
)
from project_atlas.orchestration.program.profiles import AdapterKind, AgentProfile


def _serve_fake_daemon(
    socket_path: Path, received: list[dict[str, object]]
) -> None:
    """A minimal v7 daemon fixture; socket must be live before the run."""

    def serve() -> None:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(socket_path))
        server.listen(8)
        ready.set()
        try:
            while True:
                try:
                    connection, _ = server.accept()
                except OSError:
                    break
                with connection, connection.makefile("rb") as reader:
                    try:
                        connection.sendall(
                            b'{"type":"daemon_hello","protocol":{"name":"prime-agent.daemon","version":7},"serverCapabilities":["attach_snapshot","event_sequence"]}\n'
                        )
                    except OSError:
                        continue
                    for raw in reader:
                        try:
                            envelope = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        received.append(envelope)
                        body = envelope["command"]
                        if body["type"] == "create":
                            data = {"activeSessionId": "fixture-active-1"}
                        elif body["type"] == "get_last_assistant_text":
                            data = {"text": "fixture execution complete"}
                        elif body["type"] == "get_session_stats":
                            data = {"tokens": {"input": 3, "output": 1}, "cost": 0.0}
                        else:
                            data = None
                        response = {
                            "type": "response",
                            "id": envelope["id"],
                            "command": body["type"],
                            "success": True,
                        }
                        if data is not None:
                            response["data"] = data
                        try:
                            connection.sendall((json.dumps(response) + "\n").encode())
                        except OSError:
                            break
        finally:
            server.close()

    ready = threading.Event()
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)


def _resident_request(
    tmp_path: Path,
    adapter_options: dict[str, object],
    *,
    instruction: str = "make the change",
) -> AdapterRequest:
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    options: dict[str, object] = {"provider": "fixture-provider", **adapter_options}
    profile = AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        credential="NOT_APPLICABLE",
        model="fixture-model",
        adapter_options=options,
    )
    return AdapterRequest(
        program_id="program-1",
        task_id="task-1",
        attempt_id="attempt-1",
        attempt_number=1,
        idempotency_key="key-1",
        instruction=instruction,
        workspace=workspace,
        profile=profile,
        session_id=None,
        resume_session_id=None,
        timeout_seconds=30,
        evidence_dir=tmp_path / "evidence",
    )


def _run_resident(tmp_path: Path, adapter_options: dict[str, object]) -> AdapterRequest:
    socket_path = tmp_path / "prime-daemon.sock"
    received: list[dict[str, object]] = []
    _serve_fake_daemon(socket_path, received)
    adapter = PrimeExecutorAdapter(executable="prime-agent", daemon_socket=socket_path)
    request = _resident_request(tmp_path, adapter_options)
    outcome = adapter.run(request)
    assert outcome.confidence.value == "CONFIRMED"
    assert outcome.terminal_state == "completed"
    return request


def _metadata(request: AdapterRequest) -> dict[str, object]:
    path = request.evidence_dir / f"{request.attempt_id}.prime-daemon.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_metadata_carries_policy_hash_when_configured(tmp_path: Path) -> None:
    policy = tmp_path / "trusted-policy.json"
    policy.write_text('{"tools": ["read"]}\n', encoding="utf-8")

    request = _run_resident(tmp_path, {"policy_path": str(policy)})

    assert _metadata(request)["policy_hash"] == hashlib.sha256(
        policy.read_bytes()
    ).hexdigest()


def test_metadata_policy_hash_is_none_when_unconfigured(tmp_path: Path) -> None:
    request = _run_resident(tmp_path, {})

    assert _metadata(request)["policy_hash"] is None


def test_resident_run_refuses_policy_inside_the_workspace(tmp_path: Path) -> None:
    """Workspace containment is enforced at dispatch, not in preflight.

    ``RuntimeAdapter.preflight`` receives only the profile; the resolved
    mission workspace first exists on the ``AdapterRequest``. The refusal must
    still happen before any side effect: no evidence directory may exist yet.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "policy.json").write_text("{}\n", encoding="utf-8")
    socket_path = tmp_path / "prime-daemon.sock"
    received: list[dict[str, object]] = []
    _serve_fake_daemon(socket_path, received)
    adapter = PrimeExecutorAdapter(executable="prime-agent", daemon_socket=socket_path)
    request = _resident_request(tmp_path, {"policy_path": str(workspace / "policy.json")})

    with pytest.raises(AdapterUnavailableError) as excinfo:
        adapter.run(request)

    assert excinfo.value.code == "TRUSTED_POLICY_CONTAINMENT_REFUSAL"
    assert not request.evidence_dir.exists(), "refusal must precede any side effect"


def _preflight_profile(tmp_path: Path, policy_path: Path) -> AgentProfile:
    fake = tmp_path / "prime-agent"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
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
    return AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        credential="NOT_APPLICABLE",
        model="fixture-model",
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
                "/usr",
                "/usr",
                "--chdir",
                str(workspace),
            ],
            "runtime_manifest": str(manifest),
            "provider": "fixture-provider",
            "policy_path": str(policy_path),
        },
    )


def test_preflight_refuses_a_missing_policy_file(tmp_path: Path) -> None:
    profile = _preflight_profile(tmp_path, tmp_path / "does-not-exist.json")
    adapter = PrimeExecutorAdapter(str(tmp_path / "prime-agent"))

    with pytest.raises(AdapterUnavailableError) as excinfo:
        adapter.preflight(profile)

    assert excinfo.value.code == "TRUSTED_POLICY_UNREADABLE"
    assert "regular file" in str(excinfo.value)


def test_preflight_refuses_a_directory_policy_path(tmp_path: Path) -> None:
    policy_dir = tmp_path / "policy-dir"
    policy_dir.mkdir()
    profile = _preflight_profile(tmp_path, policy_dir)
    adapter = PrimeExecutorAdapter(str(tmp_path / "prime-agent"))

    with pytest.raises(AdapterUnavailableError) as excinfo:
        adapter.preflight(profile)

    assert excinfo.value.code == "TRUSTED_POLICY_UNREADABLE"


def test_preflight_accepts_a_valid_policy_binding(tmp_path: Path) -> None:
    policy = tmp_path / "trusted-policy.json"
    policy.write_text('{"tools": ["read"]}\n', encoding="utf-8")
    profile = _preflight_profile(tmp_path, policy)
    adapter = PrimeExecutorAdapter(str(tmp_path / "prime-agent"))

    adapter.preflight(profile)
