"""HARDENING-004 fixture worker: vraagt status op TERWIJL hij zelf draait.

Zero model calls. Legt vast of een in-flight attempt door de G3-reparatie ten
onrechte als 'needs_reconciliation' wordt gemeld.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys


def main() -> int:
    workspace = pathlib.Path(os.environ.get("ATLAS_PROGRAM_WORKSPACE", "."))
    (workspace / "probe.txt").write_text("ran\n", encoding="utf-8")

    state_root = os.environ.get("ATLAS_H004_STATE_ROOT")
    out = os.environ.get("ATLAS_H004_PROBE_OUT")
    program = os.environ.get("ATLAS_H004_PROGRAM")
    if state_root and out and program:
        from project_atlas.orchestration.program.loader import load_program
        from project_atlas.orchestration.program.supervisor import ProgramSupervisor

        loaded = load_program(pathlib.Path(program))
        # Een tweede, read-only supervisor-instantie op dezelfde state: status()
        # dispatcht niets.
        probe = ProgramSupervisor(loaded, state_root=pathlib.Path(state_root))
        status = probe.status()
        recon = probe.reconcile()
        from project_atlas.orchestration.program.store import load_state

        live = load_state(pathlib.Path(state_root))
        raw = [
            {
                "attempt_id": a.attempt_id,
                "phase": a.phase.value,
                "ended_at": a.ended_at,
                "confidence": a.confidence.value if a.confidence else None,
                "process_pid": a.process_pid,
                "process_start_identity": a.process_start_identity,
            }
            for a in (live.attempts.values() if live else [])
        ]
        pathlib.Path(out).write_text(
            json.dumps(
                {
                    "needs_reconciliation": status.get("needs_reconciliation"),
                    "running": status.get("running"),
                    "reconcile_actions": [
                        (i["attempt_id"], i["recovery_action"])
                        for i in recon["interrupted_attempts"]
                    ],
                    "attempts_on_disk_DURING_run": raw,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
