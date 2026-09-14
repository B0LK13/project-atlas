"""Probe worker: reports what the child actually received, and what it can do.

Zero model calls. Spawned through the real ``local-command`` adapter, so the
environment it sees is the one ``build_child_env`` really produces -- not a
reconstruction of it.

It does the same two things the G2 and G3 fixture workers do, which is the
point: a deferred import of the program modules, and a liveness probe of its
own process. On Windows both of those depend on environment the child was not
being given. Every failure is written to the report rather than raised, so the
test that reads it can say which step broke instead of inferring it from a
missing file.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import traceback
from typing import Any


def main() -> int:
    out = os.environ.get("ATLAS_ENVPROBE_OUT")
    report: dict[str, Any] = {
        "os_name": os.name,
        "env_names": sorted(os.environ),
        "steps": {},
    }

    def record(step: str, fn: Any) -> None:
        try:
            report["steps"][step] = {"ok": True, "value": fn()}
        except BaseException:  # the report IS the diagnosis, so nothing escapes
            report["steps"][step] = {
                "ok": False,
                "traceback": traceback.format_exc(limit=6),
            }

    # 1. The deferred import both real fixture workers perform.
    def _import() -> str:
        from project_atlas.orchestration.program.control import pause

        return pause.__module__

    record("import_control", _import)

    # 2. A writable temp directory, which Windows locates from TEMP/TMP.
    def _tempdir() -> str:
        import tempfile

        return tempfile.gettempdir()

    record("gettempdir", _tempdir)

    # 3. The home directory. ntpath.expanduser reads USERPROFILE and ignores
    #    HOME, so a child given only HOME raises here on Windows.
    def _home() -> str:
        return str(pathlib.Path.home())

    record("path_home", _home)

    # 4. The two liveness primitives the recovery contract is built on. On
    #    Windows these shell out to tasklist and powershell, neither of which
    #    starts without SystemRoot.
    def _alive() -> bool:
        from project_atlas.orchestration.sdk.host import pid_is_alive

        return pid_is_alive(os.getpid())

    record("pid_is_alive_self", _alive)

    def _identity() -> str:
        from project_atlas.orchestration.sdk.host import process_start_identity

        return process_start_identity(os.getpid())

    record("process_start_identity_self", _identity)

    if out:
        pathlib.Path(out).write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
