"""SECURITY-003 fixture worker: schrijft zijn output en vraagt dan een pause.

Zero model calls. De pause komt van BUITEN de supervisor terwijl die draait,
wat de G2-reproductie deterministisch maakt zonder threads of timing.
"""

from __future__ import annotations

import os
import pathlib
import sys


def main() -> int:
    workspace = pathlib.Path(os.environ.get("ATLAS_PROGRAM_WORKSPACE", "."))
    (workspace / "first.txt").write_text("first task ran\n", encoding="utf-8")

    state_root = os.environ.get("ATLAS_SEC003_STATE_ROOT")
    if state_root:
        from project_atlas.orchestration.program.control import pause

        pause(pathlib.Path(state_root), requested_by="sec003-test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
