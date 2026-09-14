"""Disposable zero-model controller: self-exits at a production seal boundary."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from project_atlas.orchestration.program import supervisor
from project_atlas.orchestration.program.adapters.base import process_start_identity
from project_atlas.orchestration.program.resident import ResidentDispatcher

root, checkout = Path(sys.argv[1]), Path(sys.argv[2])
cut = sys.argv[3] in {"cut", "cut-final"}
cut_step = "SECOND" if sys.argv[3] == "cut-final" else "FIRST"
cut_read_only = sys.argv[3] == "cut-read-only"
print(
    json.dumps(
        {
            "pid": os.getpid(),
            "start_identity": process_start_identity(os.getpid()),
            "root": str(root),
            "executable": sys.executable,
        }
    ),
    flush=True,
)
original = supervisor.append_event


def observed_event(path: Path, name: str, body: dict[str, object]) -> object:
    result = original(path, name, body)
    if cut and name == "STEP_COMPLETED" and body["step_id"] == cut_step:
        # This interpreter terminates itself; the already-collected step child
        # is gone. No finally, destructor, signal to another PID, or state edit.
        os._exit(91)
    return result


supervisor.append_event = observed_event  # type: ignore[assignment]
if cut_read_only:
    original_recorder = supervisor.ProgramSupervisor._launch_recorder

    def recorder(self: object, attempt_id: str):  # type: ignore[no-untyped-def]
        original_callback = original_recorder(self, attempt_id)  # type: ignore[arg-type]

        def record_and_exit(pid: int, identity: str) -> None:
            original_callback(pid, identity)
            print(json.dumps({"child_pid": pid, "start_identity": identity}), flush=True)
            os._exit(91)

        return record_and_exit

    supervisor.ProgramSupervisor._launch_recorder = recorder  # type: ignore[assignment]
result = ResidentDispatcher(
    root=root,
    queue_root=root / "queue",
    checkout=checkout,
    registry_root=root / "registry",
    governed_root=root,
).tick()
print(json.dumps({"launches": result.launched, "result": repr(result)}), flush=True)
