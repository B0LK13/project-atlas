#!/usr/bin/env python3
"""D-064 overnight red-team: authorized-root / path security (frozen tip 9c71cc2).

Stand-alone — does not modify src/. Exercises refuse_dangerous_authorized_root
and discover_estate ignore / symlink policy.
"""

from __future__ import annotations

import json
import signal
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

# Ensure repo src layout is importable when run from evidence dir.
_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from project_atlas.estate_discovery import (  # noqa: E402
    EstateDiscoveryError,
    discover_estate,
    refuse_dangerous_authorized_root,
)

OUT_DIR = Path(__file__).resolve().parent
INDIVIDUAL = OUT_DIR / "redteam_path_security-results.json"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _finding(
    severity: str,
    code: str,
    detail: str,
    *,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "detail": detail,
    }
    if evidence is not None:
        row["evidence"] = evidence
    return row


class _Timeout(Exception):
    """Alarm-based timeout for symlink-loop bound check."""


def _run_symlink_loop_bounded(estate: Path, *, timeout_s: float = 5.0) -> dict[str, Any]:
    """Bound discover_estate on a symlink loop (alarm + exception capture)."""

    def _handler(_signum: int, _frame: object) -> None:
        raise _Timeout(f"exceeded {timeout_s}s bound")

    previous = signal.signal(signal.SIGALRM, _handler)
    t0 = time.monotonic()
    try:
        signal.setitimer(signal.ITIMER_REAL, timeout_s)
        try:
            report = discover_estate(estate, include_knowledge=False)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        elapsed = time.monotonic() - t0
        return {
            "completed": True,
            "hung": False,
            "elapsed_s": elapsed,
            "timeout_s": timeout_s,
            "unsafe_detected": report.get("security", {}).get(
                "unsafe_path_escapes_detected"
            ),
            "dirs_visited": report.get("scan", {}).get("dirs_visited"),
        }
    except _Timeout as exc:
        return {
            "completed": False,
            "hung": True,
            "elapsed_s": time.monotonic() - t0,
            "timeout_s": timeout_s,
            "error_type": "Timeout",
            "error": str(exc),
        }
    except Exception as exc:  # noqa: BLE001 — red-team boundary
        return {
            "completed": False,
            "hung": False,
            "elapsed_s": time.monotonic() - t0,
            "timeout_s": timeout_s,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(limit=5),
        }
    finally:
        signal.signal(signal.SIGALRM, previous)


def run() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}

    # --- Hard counters (must be 0 for PASS) ---
    unsafe_path_escapes_allowed = 0
    whole_disk_scan = 0  # 1 if / was accepted / scanned
    home_directory_silent_scan = 0  # 1 if home was accepted / scanned

    # 1) Refuse filesystem root
    try:
        refuse_dangerous_authorized_root(Path("/"))
        whole_disk_scan = 1
        findings.append(
            _finding(
                "HIGH",
                "WHOLE_DISK_SCAN_ALLOWED",
                "filesystem root accepted as authorized discovery root",
            )
        )
        checks["refuse_filesystem_root"] = "FAIL"
    except EstateDiscoveryError as exc:
        checks["refuse_filesystem_root"] = {
            "result": "PASS",
            "error": str(exc),
        }
    # Also refuse via discover_estate entry
    try:
        discover_estate(Path("/"), include_knowledge=False)
        whole_disk_scan = 1
        findings.append(
            _finding(
                "HIGH",
                "WHOLE_DISK_SCAN_VIA_DISCOVER",
                "discover_estate('/') did not refuse",
            )
        )
    except EstateDiscoveryError:
        checks["discover_refuse_filesystem_root"] = "PASS"
    except Exception as exc:  # noqa: BLE001
        findings.append(
            _finding(
                "HIGH",
                "WHOLE_DISK_SCAN_UNEXPECTED_ERROR",
                f"discover_estate('/') raised {type(exc).__name__}: {exc}",
            )
        )
        checks["discover_refuse_filesystem_root"] = "FAIL"

    # 2) Refuse home directory
    home = Path.home()
    try:
        refuse_dangerous_authorized_root(home)
        home_directory_silent_scan = 1
        findings.append(
            _finding(
                "HIGH",
                "HOME_DIRECTORY_SILENT_SCAN",
                f"home directory accepted as authorized root: {home}",
            )
        )
        checks["refuse_home"] = "FAIL"
    except EstateDiscoveryError as exc:
        checks["refuse_home"] = {"result": "PASS", "error": str(exc)}
    try:
        discover_estate(home, include_knowledge=False)
        home_directory_silent_scan = 1
        findings.append(
            _finding(
                "HIGH",
                "HOME_DIRECTORY_SILENT_SCAN_VIA_DISCOVER",
                "discover_estate(home) did not refuse",
            )
        )
    except EstateDiscoveryError:
        checks["discover_refuse_home"] = "PASS"
    except Exception as exc:  # noqa: BLE001
        findings.append(
            _finding(
                "HIGH",
                "HOME_SCAN_UNEXPECTED_ERROR",
                f"discover_estate(home) raised {type(exc).__name__}: {exc}",
            )
        )
        checks["discover_refuse_home"] = "FAIL"

    with tempfile.TemporaryDirectory(prefix="d064-path-") as tmp:
        base = Path(tmp)
        estate = base / "estate"
        outside = base / "outside-secret"
        outside.mkdir(parents=True)
        _write(outside / "SECRET.txt", "OUTSIDE_TOPSECRET_SHOULD_NOT_LEAK\n")

        estate.mkdir()
        good = estate / "good-project"
        _write(good / "README.md", "# good\n")
        (good / ".git").mkdir(parents=True)
        (good / "src").mkdir(parents=True)

        # Symlink escape outside estate
        escape = estate / "escape-link"
        escape.symlink_to(outside)

        # Nested .git internals with fake project signals
        nested_git_fake = good / ".git" / "objects" / "fake-nested-project"
        _write(nested_git_fake / "README.md", "# nested fake\n")
        (nested_git_fake / ".git").mkdir(parents=True)
        (nested_git_fake / "src").mkdir(parents=True)
        _write(nested_git_fake / "package.json", '{"name":"fake-nested"}\n')

        # .atlas-vault ignored fake project
        atlas_vault_fake = estate / ".atlas-vault" / "vault-fake-project"
        _write(atlas_vault_fake / "README.md", "# vault fake\n")
        (atlas_vault_fake / ".git").mkdir(parents=True)
        (atlas_vault_fake / "src").mkdir(parents=True)
        _write(atlas_vault_fake / "package.json", '{"name":"vault-fake"}\n')

        # node_modules fake-project ignored
        nm_fake = good / "node_modules" / "fake-project"
        _write(nm_fake / "README.md", "# nm fake\n")
        (nm_fake / ".git").mkdir(parents=True)
        (nm_fake / "src").mkdir(parents=True)
        _write(nm_fake / "package.json", '{"name":"fake-project"}\n')

        report = discover_estate(estate, include_knowledge=False)
        security = report.get("security") or {}
        allowed = int(security.get("unsafe_path_escapes_allowed") or 0)
        detected = int(security.get("unsafe_path_escapes_detected") or 0)
        unsafe_path_escapes_allowed = allowed

        project_names = {
            Path(p["path"]).name for p in report.get("candidates", {}).get("projects", [])
        }
        project_paths = [
            p["path"] for p in report.get("candidates", {}).get("projects", [])
        ]
        ignored = report.get("categories", {}).get("IGNORED") or []
        ignored_paths = {row.get("path", "") for row in ignored if isinstance(row, dict)}
        ignored_reasons = {
            row.get("path", ""): row.get("reason", "")
            for row in ignored
            if isinstance(row, dict)
        }
        blob = json.dumps(report, sort_keys=True)

        checks["symlink_escape"] = {
            "detected": detected,
            "allowed": allowed,
            "escape_ignored": any(
                "escape-link" in (row.get("path") or "")
                and "escape" in (row.get("reason") or "")
                for row in ignored
                if isinstance(row, dict)
            ),
            "outside_as_candidate": any("outside-secret" in p for p in project_paths),
            "outside_secret_in_report": "OUTSIDE_TOPSECRET_SHOULD_NOT_LEAK" in blob,
        }
        if allowed != 0:
            findings.append(
                _finding(
                    "HIGH",
                    "UNSAFE_PATH_ESCAPES_ALLOWED",
                    f"security.unsafe_path_escapes_allowed={allowed}",
                    evidence={"detected": detected},
                )
            )
        if detected < 1:
            findings.append(
                _finding(
                    "HIGH",
                    "SYMLINK_ESCAPE_NOT_DETECTED",
                    "symlink escape outside estate was not counted as unsafe escape",
                    evidence=checks["symlink_escape"],
                )
            )
        if checks["symlink_escape"]["outside_as_candidate"]:
            unsafe_path_escapes_allowed = max(unsafe_path_escapes_allowed, 1)
            findings.append(
                _finding(
                    "HIGH",
                    "SYMLINK_ESCAPE_CANDIDATE_EMITTED",
                    "project candidate path resolves under outside-secret",
                )
            )
        if checks["symlink_escape"]["outside_secret_in_report"]:
            findings.append(
                _finding(
                    "HIGH",
                    "SYMLINK_ESCAPE_CONTENT_LEAK",
                    "secret content from outside estate appeared in discovery report JSON",
                )
            )

        # Nested .git internals ignored (no descend into .git)
        nested_name = "fake-nested-project"
        checks["nested_git_internals_ignored"] = nested_name not in project_names
        if nested_name in project_names:
            findings.append(
                _finding(
                    "HIGH",
                    "NESTED_GIT_INTERNALS_PROJECT",
                    "fake project under .git/objects was emitted as a candidate",
                )
            )

        # .atlas-vault ignored
        checks["atlas_vault_ignored"] = {
            "fake_not_candidate": "vault-fake-project" not in project_names,
            "dir_ignored": any(
                p.endswith("/.atlas-vault") or p.endswith(".atlas-vault")
                for p in ignored_paths
            ),
        }
        if "vault-fake-project" in project_names:
            findings.append(
                _finding(
                    "HIGH",
                    "ATLAS_VAULT_NOT_IGNORED",
                    ".atlas-vault fake project was emitted as a candidate",
                )
            )

        # node_modules fake-project ignored
        checks["node_modules_fake_ignored"] = "fake-project" not in project_names
        if "fake-project" in project_names:
            findings.append(
                _finding(
                    "HIGH",
                    "NODE_MODULES_FAKE_PROJECT",
                    "node_modules/fake-project was emitted as a project candidate",
                )
            )
        if "good-project" not in project_names:
            findings.append(
                _finding(
                    "HIGH",
                    "LEGITIMATE_PROJECT_MISSING",
                    "expected good-project candidate missing — suite invalid",
                    evidence={"project_names": sorted(project_names)},
                )
            )

        checks["ignore_reasons_sample"] = {
            k: ignored_reasons[k]
            for k in sorted(ignored_reasons)
            if any(
                token in k
                for token in (
                    "escape-link",
                    ".atlas-vault",
                    "node_modules",
                    ".git",
                )
            )
        }

        # Symlink loop — must not hang infinitely; must be bounded
        loop_estate = base / "loop-estate"
        loop_estate.mkdir()
        _write(loop_estate / "anchor" / "README.md", "# anchor\n")
        (loop_estate / "anchor" / ".git").mkdir(parents=True)
        loop_dir = loop_estate / "loop"
        loop_dir.mkdir()
        (loop_dir / "x").symlink_to(loop_dir / "y")
        (loop_dir / "y").symlink_to(loop_dir / "x")
        loop_result = _run_symlink_loop_bounded(loop_estate, timeout_s=5.0)
        checks["symlink_loop"] = loop_result
        if loop_result.get("hung"):
            findings.append(
                _finding(
                    "HIGH",
                    "SYMLINK_LOOP_UNBOUNDED",
                    "discover_estate hung on symlink loop beyond timeout bound",
                    evidence=loop_result,
                )
            )
        elif not loop_result.get("completed"):
            # Crash / uncaught RuntimeError is a HIGH fail-closed gap:
            # policy requires bound handling, not process abort.
            findings.append(
                _finding(
                    "HIGH",
                    "SYMLINK_LOOP_UNBOUNDED",
                    "discover_estate crashed on symlink loop instead of "
                    "bounded ignore/detect",
                    evidence={
                        "error_type": loop_result.get("error_type"),
                        "error": loop_result.get("error"),
                    },
                )
            )
        else:
            checks["symlink_loop"]["result"] = "PASS"

    hard_counters = {
        "UNSAFE_PATH_ESCAPES_ALLOWED": unsafe_path_escapes_allowed,
        "WHOLE_DISK_SCAN": whole_disk_scan,
        "HOME_DIRECTORY_SILENT_SCAN": home_directory_silent_scan,
    }
    high = [f for f in findings if f["severity"] == "HIGH"]
    hard_ok = all(v == 0 for v in hard_counters.values())
    status = "PASS" if hard_ok and not high else "FAIL"

    result: dict[str, Any] = {
        "script": "redteam_path_security.py",
        "frozen_tip": "9c71cc2",
        "status": status,
        "hard_counters": hard_counters,
        "checks": checks,
        "findings": findings,
        "high_findings": len(high),
    }
    return result


def main() -> int:
    result = run()
    INDIVIDUAL.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "PASS" or result["high_findings"]:
        return 1
    if any(v != 0 for v in result["hard_counters"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
