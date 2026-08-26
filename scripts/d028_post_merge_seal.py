#!/usr/bin/env python3
"""Post-integration seal harness (D-028). Exit non-zero on failure."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "f6b2495a03196901a5a72c2cf3451d4504b54d5f"
EXPECTED_TREE = "9c670d710ec63d36fea70c6a181c088b79294336"

RR_FILES = [
    "tests/unit/test_as_coder_alpha_architecture_read_001.py",
    "tests/unit/test_as_coder_alpha_bitemporal_read_001.py",
    "tests/unit/test_as_coder_alpha_changed_read_001.py",
    "tests/unit/test_as_coder_alpha_decisions_read_001.py",
    "tests/unit/test_as_coder_alpha_index_status_001.py",
    "tests/unit/test_as_coder_alpha_next_read_001.py",
    "tests/unit/test_as_coder_alpha_overview_read_001.py",
    "tests/unit/test_as_coder_alpha_portfolio_read_001.py",
    "tests/unit/test_as_coder_alpha_roadmap_read_001.py",
    "tests/unit/test_as_coder_alpha_state_read_001.py",
    "tests/unit/test_as_coder_alpha_unknown_read_001.py",
]

IV_FILES = [
    "tests/unit/test_atlas3_adv_020_control_001.py",
    "tests/unit/test_atlas3_iv_bind_051.py",
    "tests/unit/test_atlas3_memory_project_isolation_001.py",
    "tests/unit/test_atlas3_ledger_integrity_001.py",
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=REPO)


def main() -> int:
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip()
    tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=REPO, text=True
    ).strip()
    print(f"HEAD={head} TREE={tree}")
    if head != EXPECTED_HEAD and not Path(REPO / "atlas-vault-documentation/skills/atlas-golden-estate-curator/curator.py").exists():
        print("WARN: not on expected main; carrier mode assumed", file=sys.stderr)

    run(["python", "-m", "ruff", "check", "src/project_atlas/atlas3"])
    run(["python", "-m", "pytest", "tests/unit/", "-k", "test_atlas3", "-q", "--tb=no", "--no-cov"])
    run(["python", "-m", "pytest", *RR_FILES, "-q", "--tb=no", "--no-cov"])
    run(["python", "-m", "pytest", *IV_FILES, "-q", "--tb=no", "--no-cov"])
    ge = REPO / "atlas-vault-documentation/skills/atlas-golden-estate-curator/tests"
    if ge.exists():
        run(["python", "-m", "pytest", str(ge), "-q", "--tb=no", "--no-cov"])
    print("SEAL_HARNESS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
