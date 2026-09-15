#!/usr/bin/env python3
"""D-064 overnight red-team: secrets must not leak into estate discovery reports.

Frozen tip 9c71cc2. Stand-alone — does not modify src/.

Plants fake secrets in files and a git remote URL with embedded credentials.
Scans the discover_estate report JSON string for substrings that must not leak.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from project_atlas.estate_discovery import discover_estate  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
INDIVIDUAL = OUT_DIR / "redteam_secrets_privacy-results.json"

# Planted secret material (synthetic; never real credentials).
PLANTED_REMOTE_PASSWORD = "SECRETKEY"
PLANTED_REMOTE_URL = (
    f"https://user:{PLANTED_REMOTE_PASSWORD}@example.com/repo.git"
)
PLANTED_API_KEY = "sk-planted-ABCDEF1234567890XYZ"
PLANTED_PEM_BODY = (
    "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7PlantedFake"
    "PemBodyMaterialForRedTeamOnlyNotARealKey000111222333444555666777"
)
PLANTED_PEM_BLOCK = (
    "-----BEGIN PRIVATE KEY-----\n"
    f"{PLANTED_PEM_BODY}\n"
    "-----END PRIVATE KEY-----\n"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _finding(
    severity: str, code: str, detail: str, *, evidence: dict[str, Any] | None = None
) -> dict[str, Any]:
    row: dict[str, Any] = {"severity": severity, "code": code, "detail": detail}
    if evidence is not None:
        row["evidence"] = evidence
    return row


def _password_in_url(text: str) -> list[str]:
    """Return credential-bearing URL substrings (user:pass@host)."""
    return re.findall(r"https?://[^/\s\"']+:[^/\s\"']+@[^/\s\"']+", text)


def run() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}

    secret_leaks = 0
    remote_password_echo = 0
    pem_body_leaks = 0
    api_key_leaks = 0

    with tempfile.TemporaryDirectory(prefix="d064-secrets-") as tmp:
        base = Path(tmp)
        estate = base / "estate"
        proj = estate / "cred-svc"
        _write(
            proj / "README.md",
            "# cred-svc\n\n"
            f"Do not commit: API_KEY={PLANTED_API_KEY}\n"
            "Another line: Authorization: Bearer PLANTED_BEARER_TOKEN_XYZ\n",
        )
        _write(proj / "secrets-note.md", PLANTED_PEM_BLOCK)
        # markdown cluster so knowledge may pick up notes if policy allows
        _write(proj / "a.md", "note a\n")
        _write(proj / "b.md", "note b\n")
        (proj / ".git").mkdir(parents=True)
        _write(
            proj / ".git" / "config",
            f'[remote "origin"]\n\turl = {PLANTED_REMOTE_URL}\n',
        )
        _write(proj / "package.json", '{"name":"cred-svc"}\n')
        (proj / "src").mkdir(parents=True)

        report = discover_estate(estate, include_knowledge=True)
        # Public report surface (exclude private _cache_entries like write_discovery_report)
        public = {k: v for k, v in report.items() if not str(k).startswith("_")}
        report_json = json.dumps(public, indent=2, sort_keys=True)
        full_json = json.dumps(report, indent=2, sort_keys=True)

        projects = report.get("candidates", {}).get("projects") or []
        git_remote = None
        if projects:
            git_remote = (projects[0].get("fingerprint") or {}).get("git_remote")

        checks["git_remote_observed"] = git_remote
        checks["project_count"] = len(projects)

        # SECRETKEY from remote password
        if PLANTED_REMOTE_PASSWORD in report_json:
            secret_leaks += 1
            remote_password_echo += 1
            findings.append(
                _finding(
                    "HIGH",
                    "GIT_REMOTE_PASSWORD_ECHO",
                    "planted remote password SECRETKEY appears in discovery report JSON",
                    evidence={"git_remote": git_remote},
                )
            )

        # Credential-bearing URL pattern anywhere in report
        cred_urls = sorted(set(_password_in_url(report_json)))
        checks["credential_urls_in_report"] = cred_urls
        if cred_urls:
            remote_password_echo = max(remote_password_echo, 1)
            if not any(f["code"] == "GIT_REMOTE_PASSWORD_ECHO" for f in findings):
                findings.append(
                    _finding(
                        "HIGH",
                        "GIT_REMOTE_PASSWORD_ECHO",
                        "report contains user:password@ URL material",
                        evidence={"matches": cred_urls},
                    )
                )
            secret_leaks = max(secret_leaks, 1)

        # API key planted in README — must not echo
        if PLANTED_API_KEY in report_json:
            api_key_leaks += 1
            secret_leaks += 1
            findings.append(
                _finding(
                    "HIGH",
                    "API_KEY_LEAK",
                    "planted API key from README appeared in discovery report JSON",
                )
            )
        checks["api_key_in_report"] = PLANTED_API_KEY in report_json

        # PEM body must not appear
        if PLANTED_PEM_BODY in report_json:
            pem_body_leaks += 1
            secret_leaks += 1
            findings.append(
                _finding(
                    "HIGH",
                    "PEM_BODY_LEAK",
                    "planted PEM private-key body appeared in discovery report JSON",
                )
            )
        if "BEGIN PRIVATE KEY" in report_json:
            pem_body_leaks += 1
            secret_leaks += 1
            findings.append(
                _finding(
                    "HIGH",
                    "PEM_HEADER_LEAK",
                    "PEM header text appeared in discovery report JSON",
                )
            )
        checks["pem_body_in_report"] = PLANTED_PEM_BODY in report_json
        checks["pem_header_in_report"] = "BEGIN PRIVATE KEY" in report_json

        # Also flag if private _cache_entries somehow carried secrets (defense)
        checks["secretkey_in_full_including_private"] = (
            PLANTED_REMOTE_PASSWORD in full_json
        )

        # Sanitized remote would omit password; presence of password is the finding.
        if isinstance(git_remote, str) and PLANTED_REMOTE_PASSWORD in git_remote:
            checks["remote_sanitized"] = False
        elif git_remote is None:
            checks["remote_sanitized"] = None
            findings.append(
                _finding(
                    "MEDIUM",
                    "GIT_REMOTE_ABSENT",
                    "git_remote missing from fingerprint — cannot prove sanitization",
                )
            )
        else:
            checks["remote_sanitized"] = PLANTED_REMOTE_PASSWORD not in str(git_remote)

    hard_counters = {
        "SECRET_LEAKS": secret_leaks,
        "REMOTE_PASSWORD_ECHO": remote_password_echo,
        "API_KEY_LEAKS": api_key_leaks,
        "PEM_BODY_LEAKS": pem_body_leaks,
    }
    high = [f for f in findings if f["severity"] == "HIGH"]
    hard_ok = all(v == 0 for v in hard_counters.values())
    status = "PASS" if hard_ok and not high else "FAIL"

    return {
        "script": "redteam_secrets_privacy.py",
        "frozen_tip": "9c71cc2",
        "status": status,
        "hard_counters": hard_counters,
        "checks": checks,
        "findings": findings,
        "high_findings": len(high),
        "planted": {
            "remote_url_template": "https://user:***@example.com/repo.git",
            "api_key_prefix": PLANTED_API_KEY[:12] + "...",
            "pem_body_prefix": PLANTED_PEM_BODY[:24] + "...",
        },
    }


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
