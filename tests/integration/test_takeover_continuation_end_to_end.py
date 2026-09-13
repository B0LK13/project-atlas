"""TAKEOVER-001: exercise actual dispatcher processes, workers and resume."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.parametrize("scenario", ["complete", "revoked", "uncertain"])
def test_continuation_installed_or_source_chain(tmp_path: Path, scenario: str) -> None:
    checkout = Path(__file__).resolve().parents[2]
    root = tmp_path / "demo"
    result = subprocess.run(
        [sys.executable, str(checkout / "scripts/atlas_takeover_demo.py"),
         "--checkout", str(checkout), "--root", str(root), "--scenario", scenario,
         "--allow-source"],
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads((root / "result.json").read_text())
    assert evidence["result"] == "PASS"
    assert evidence["launches"] == ([1, 0, 1, 0] if scenario == "complete" else [1, 0, 0, 0])
    assert evidence["owned_worker_survivors"] == []
    assert len(set(evidence["dispatcher_pids"])) == 4
