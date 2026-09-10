"""Fixture worker for TestAcquireIsNowAtomicNotCheckThenWrite: a real,
independent OS process (a genuine, distinct pid) that tries once to acquire
the resident-driver primary lock at the path given on the command line, and
prints ACQUIRED or REFUSED. No model calls, no other side effects.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(REPO_SRC))

from project_atlas.orchestration.sdk.resident_driver import acquire_primary_lock  # noqa: E402

if __name__ == "__main__":
    root = Path(sys.argv[1])
    print("ACQUIRED" if acquire_primary_lock(root) else "REFUSED")
