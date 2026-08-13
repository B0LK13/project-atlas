#!/usr/bin/env python3
"""D-064 overnight: corrupt identity / marker inputs must not EXACT-match.

Cases:
- invalid UUID in .atlas-project.yaml
- malformed YAML marker
- binary / NUL marker content (unreadable)

Expectation: CONFLICTING and/or required_review; never EXACT via weaker evidence.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from project_atlas.estate_discovery import discover_estate

OUT_DIR = Path(__file__).resolve().parent
RESULT_PATH = OUT_DIR / "corrupt_input.result.json"

ALPHA_UUID = "11111111-1111-4111-8111-111111111111"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _allocation(vault: Path, project_id: str, project_uuid: str) -> None:
    path = (
        vault
        / "receipts"
        / "source-lineage"
        / f"project-{project_id}-allocation.json"
    )
    _write(
        path,
        json.dumps(
            {
                "schema_version": 1,
                "receipt_type": "project-identity-allocation",
                "project": project_id,
                "project_uuid": project_uuid,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def _project_shell(root: Path) -> None:
    _write(root / "README.md", f"# {root.name}\n")
    _write(root / "pyproject.toml", f'[project]\nname = "{root.name}"\n')
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / ".git").mkdir(parents=True, exist_ok=True)


def build_fixture(base: Path) -> tuple[Path, Path, dict[str, str]]:
    """Estate with three corrupt marker projects + governed vault alpha."""
    estate = base / "estate"
    vault = base / "vault"

    invalid_uuid = estate / "corrupt-invalid-uuid"
    _project_shell(invalid_uuid)
    _write(
        invalid_uuid / ".atlas-project.yaml",
        "project:\n  id: alpha\nproject_uuid: not-a-uuid\n",
    )

    malformed = estate / "corrupt-malformed-yaml"
    _project_shell(malformed)
    # Directory name + package align with vault id — weaker evidence must not win.
    _write(malformed / "pyproject.toml", '[project]\nname = "alpha"\n')
    _write(
        malformed / ".atlas-project.yaml",
        "project: [unterminated\n  id: alpha\n:::: not yaml {{{\n",
    )

    binary_nul = estate / "corrupt-binary-nul"
    _project_shell(binary_nul)
    _write(binary_nul / "pyproject.toml", '[project]\nname = "alpha"\n')
    # NUL bytes → _safe_read_text returns None → marker_status unreadable.
    _write_bytes(
        binary_nul / ".atlas-project.yaml",
        b"project:\n  id: alpha\nproject_uuid: "
        + ALPHA_UUID.encode("ascii")
        + b"\n\x00\xffBINARY",
    )

    (vault / "projects" / "alpha").mkdir(parents=True)
    _allocation(vault, "alpha", ALPHA_UUID)
    _write(
        vault / "projects" / "alpha" / "project.md",
        f"---\nproject_uuid: {ALPHA_UUID}\n---\n",
    )

    labels = {
        invalid_uuid.name: "invalid_uuid",
        malformed.name: "malformed_yaml",
        binary_nul.name: "binary_nul_marker",
    }
    return estate, vault, labels


def evaluate_case(candidate: dict[str, Any], label: str) -> dict[str, Any]:
    match_state = candidate.get("match_state")
    required_review = bool(candidate.get("required_review"))
    conflicting = candidate.get("conflicting_evidence") or []
    fingerprint = candidate.get("fingerprint") or {}
    false_exact = match_state == "EXACT"
    # Weaker-evidence false match: EXACT despite corrupt marker/uuid.
    marker_status = fingerprint.get("marker_status")
    uuid_status = fingerprint.get("uuid_status")
    corrupt_ok = (
        match_state == "CONFLICTING"
        and required_review
        and isinstance(conflicting, list)
        and len(conflicting) > 0
    )
    return {
        "label": label,
        "path": candidate.get("path"),
        "candidate_id": candidate.get("candidate_id"),
        "match_state": match_state,
        "category": candidate.get("category"),
        "required_review": required_review,
        "marker_status": marker_status,
        "uuid_status": uuid_status,
        "conflicting_evidence": conflicting,
        "why_matched": candidate.get("why_matched"),
        "false_exact": false_exact,
        "pass": corrupt_ok and not false_exact,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="d064-corrupt-") as tmp:
        estate, vault, labels = build_fixture(Path(tmp))
        report = discover_estate(estate, vault=vault, include_knowledge=False)
        projects = (report.get("candidates") or {}).get("projects") or []
        by_name = {Path(p["path"]).name: p for p in projects if isinstance(p, dict)}

        cases: list[dict[str, Any]] = []
        missing: list[str] = []
        false_matches = 0
        for dirname, label in labels.items():
            cand = by_name.get(dirname)
            if cand is None:
                missing.append(dirname)
                false_matches += 1
                cases.append(
                    {
                        "label": label,
                        "path": dirname,
                        "pass": False,
                        "false_exact": False,
                        "error": "candidate_not_discovered",
                    }
                )
                continue
            row = evaluate_case(cand, label)
            if row["false_exact"] or not row["pass"]:
                false_matches += 1
            cases.append(row)

        # Extra guard: no project candidate in this corrupt estate may be EXACT.
        exact_anywhere = [
            {
                "candidate_id": p.get("candidate_id"),
                "path": p.get("path"),
                "match_state": p.get("match_state"),
            }
            for p in projects
            if isinstance(p, dict) and p.get("match_state") == "EXACT"
        ]
        false_matches += len(exact_anywhere)

        result = {
            "schema": "d064-overnight-corrupt-input-v1",
            "package_id": "AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001",
            "cases": cases,
            "exact_anywhere": exact_anywhere,
            "missing_candidates": missing,
            "report_counts": report.get("counts"),
            "counters": {
                "CORRUPT_IDENTITY_FALSE_MATCH": false_matches,
            },
            "pass": false_matches == 0 and not missing and all(c.get("pass") for c in cases),
        }

        RESULT_PATH.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(result["counters"], indent=2, sort_keys=True))
        print(f"wrote {RESULT_PATH}")
        print(f"pass={result['pass']}")
        return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
