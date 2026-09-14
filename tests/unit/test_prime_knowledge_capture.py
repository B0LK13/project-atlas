"""Knowledge-capture route and context-delivery pins for the Prime adapter.

The capture file is LOCAL EVIDENCE ONLY: ``sync_state`` is pinned to
``pending_local_evidence_not_canonical`` so a reader can never mistake the row
for a canonical Knowledge Plane receipt (that pipeline row stays OPEN). The
context-delivery pin proves the resident path hands the daemon exactly
``AdapterRequest.instruction``, verbatim, with no truncation or digesting.
"""

from __future__ import annotations

import json
import socket
import stat
import threading
from pathlib import Path

from project_atlas.orchestration.program.adapters.base import (
    AdapterOutcome,
    AdapterRequest,
)
from project_atlas.orchestration.program.adapters.prime_agent import PrimeExecutorAdapter
from project_atlas.orchestration.program.profiles import AdapterKind, AgentProfile


def _serve_fake_daemon(
    socket_path: Path, received: list[dict[str, object]]
) -> None:
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


def _run_resident(
    tmp_path: Path,
    received: list[dict[str, object]],
    *,
    instruction: str,
    socket_path: Path | None = None,
) -> tuple[AdapterRequest, AdapterOutcome]:
    if socket_path is None:
        socket_path = tmp_path / "prime-daemon.sock"
        _serve_fake_daemon(socket_path, received)
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    profile = AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        credential="NOT_APPLICABLE",
        model="fixture-model",
        adapter_options={"provider": "fixture-provider"},
    )
    request = AdapterRequest(
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
    outcome = PrimeExecutorAdapter(
        executable="prime-agent", daemon_socket=socket_path
    ).run(request)
    assert outcome.confidence.value == "CONFIRMED"
    assert outcome.terminal_state == "completed"
    return request, outcome


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_resident_run_appends_local_evidence_capture_row(tmp_path: Path) -> None:
    """The capture row is honest local evidence: complete fields, 0600, and
    nothing written anywhere outside evidence_dir — in particular no
    canonical/knowledge-plane directories are minted by this route."""
    socket_path = tmp_path / "prime-daemon.sock"
    received: list[dict[str, object]] = []
    _serve_fake_daemon(socket_path, received)
    before = _snapshot(tmp_path)  # the socket file belongs to the fixture

    request, _ = _run_resident(
        tmp_path, received, instruction="make the change", socket_path=socket_path
    )
    evidence = request.evidence_dir.resolve()

    capture_path = request.evidence_dir / "prime-knowledge-capture.jsonl"
    assert capture_path.is_file()
    assert stat.S_IMODE(capture_path.stat().st_mode) == 0o600
    lines = capture_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, "one attempt appends exactly one capture row"
    event = json.loads(lines[0])

    transcript_lines = (
        request.evidence_dir / "attempt-1.prime-daemon.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    assert event == {
        "event_id": "KE-attempt-1",
        "recorded_at": None,
        "event_seq": len(transcript_lines),
        "adapter": "prime-agent",
        "mission_id": "program-1",
        "task_id": "task-1",
        "attempt_id": "attempt-1",
        "candidate_sha": None,
        "tree_sha": None,
        "workspace_identity": str(request.workspace.resolve()),
        "prime_session_id": None,
        "prime_active_session_id": "fixture-active-1",
        "outcome": "completed",
        "stop_reason": None,
        "sync_state": "pending_local_evidence_not_canonical",
    }
    assert event["event_seq"] >= 1

    after = _snapshot(tmp_path)
    new_paths = sorted(set(after) - set(before))
    assert new_paths, "the run must have written evidence"
    for relative in new_paths:
        assert (tmp_path / relative).resolve().is_relative_to(evidence), (
            f"write escaped evidence_dir: {relative}"
        )


def test_capture_row_is_listed_in_attempt_evidence(tmp_path: Path) -> None:
    received: list[dict[str, object]] = []
    request, outcome = _run_resident(tmp_path, received, instruction="make the change")

    assert "prime-knowledge-capture.jsonl" in outcome.evidence
    metadata = json.loads(
        (request.evidence_dir / "attempt-1.prime-daemon.json").read_text(
            encoding="utf-8"
        )
    )
    assert metadata["attempt_id"] == "attempt-1"


def test_prompt_payload_carries_the_instruction_verbatim(tmp_path: Path) -> None:
    """Context delivery: the daemon receives exactly AdapterRequest.instruction.

    The wire sends the message string verbatim inside the prompt_and_wait
    command (no truncation, no digest), so equality is asserted verbatim
    against a long, non-ASCII instruction.
    """
    instruction = "repair the parser — " + ("x" * 5000) + " 🚀"
    received: list[dict[str, object]] = []
    _run_resident(tmp_path, received, instruction=instruction)

    prompts = [
        envelope["command"]
        for envelope in received
        if envelope["command"]["type"] == "prompt_and_wait"
    ]
    assert len(prompts) == 1
    assert prompts[0]["message"] == instruction
