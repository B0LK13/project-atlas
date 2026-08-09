#!/usr/bin/env python3
"""Run the AS-ADV clean-clone fixture rehearsal in disposable storage only."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

CASE_ID = "clean_clone_replay"


class RehearsalError(RuntimeError):
    """Raised when the rehearsal cannot prove its fixture-only assertions."""


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _assert_disposable_root(root: Path, *, repo_root: Path) -> None:
    system_temp = Path(tempfile.gettempdir()).resolve()
    forbidden = {Path(root.anchor).resolve(), Path.home().resolve(), repo_root}
    if root in forbidden:
        raise RehearsalError(f"refusing unsafe scratch root: {root}")
    if not _is_relative_to(root, system_temp):
        raise RehearsalError("scratch root is outside the operating-system temp directory")
    if _is_relative_to(root, repo_root) or _is_relative_to(repo_root, root):
        raise RehearsalError("scratch root overlaps the repository")


def _load_report(stdout: str) -> dict[str, Any]:
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RehearsalError("atlas CLI did not return a JSON report") from exc
    if not isinstance(report, dict):
        raise RehearsalError("atlas CLI report is not a JSON object")
    return report


def _assert_nonclaims(report: dict[str, Any]) -> None:
    required_false = (
        "release_certified",
        "estate_pilot_passed",
        "web_application_accepted",
    )
    for field in required_false:
        if report.get(field) is not False:
            raise RehearsalError(f"fail-closed: report field {field!r} is not false")


def _assert_clean_clone_pass(report: dict[str, Any]) -> None:
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise RehearsalError("report cases are missing or malformed")
    matches = [row for row in cases if isinstance(row, dict) and row.get("case_id") == CASE_ID]
    if len(matches) != 1:
        raise RehearsalError("report must contain exactly one clean_clone_replay row")
    if matches[0].get("result") != "pass":
        raise RehearsalError("clean_clone_replay did not pass")


def run_rehearsal() -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    source_root = repo_root / "src"
    if not (source_root / "project_atlas" / "cli.py").is_file():
        raise RehearsalError("run this helper from a Project Atlas source checkout")

    with tempfile.TemporaryDirectory(prefix="atlas-adv-clean-clone-") as temp_name:
        scratch = Path(temp_name).resolve()
        _assert_disposable_root(scratch, repo_root=repo_root)
        work_root = scratch / "work"
        command = [
            sys.executable,
            "-m",
            "project_atlas.cli",
            "adv",
            "certify",
            "--work-root",
            str(work_root),
            "--json",
        ]
        environment = os.environ.copy()
        existing_pythonpath = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(source_root), existing_pythonpath) if part
        )
        completed = subprocess.run(
            command,
            cwd=repo_root,
            env=environment,
            capture_output=True,
            check=False,
            text=True,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "atlas adv certify returned non-zero"
            raise RehearsalError(detail)
        report = _load_report(completed.stdout)
        _assert_nonclaims(report)
        _assert_clean_clone_pass(report)
        return report


def main() -> int:
    try:
        report = run_rehearsal()
    except (OSError, RehearsalError) as exc:
        print(f"REHEARSAL=FAIL: {exc}", file=sys.stderr)
        return 1
    clean_clone = next(row for row in report["cases"] if row["case_id"] == CASE_ID)
    print(f"REHEARSAL=PASS case={CASE_ID} result={clean_clone['result']}")
    print("RELEASE=NO")
    print("PILOT=NO")
    print("WEB ACCEPTED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
