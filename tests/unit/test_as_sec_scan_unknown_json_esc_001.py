"""AS-SEC-SCAN-UNKNOWN-JSON-ESC-001 — scan decoded semantic-record scalars.

Unknown/state lenses ``json.loads`` the ``## Semantic record`` fence. Quoted
``\\u`` escapes miss raw ``scan_text`` and must not persist as coverage or
lifecycle. Distinct persist sink from estate-discovery YAML (#945) and
ask2 provenance echo (#888).
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.project_state import materialize_state_lenses
from project_atlas.project_unknown import materialize_unknown_lenses
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"  # AKIA + 16 A — matches cloud-access-key


def _vault_with_escaped_semantic(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    note = vault / "projects" / "demo" / "project.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "# demo\n\n"
        "## Semantic record\n"
        "```json\n"
        '{"coverage":[{"state":"absent","category":"\\u0041KIAAAAAAAAAAAAAAAAA"}],'
        '"lifecycle":"\\u0041KIAAAAAAAAAAAAAAAAA"}\n'
        "```\n",
        encoding="utf-8",
    )
    return vault


def test_unicode_escape_category_is_not_in_unknown_lens(tmp_path: Path) -> None:
    vault = _vault_with_escaped_semantic(tmp_path)
    raw = (vault / "projects" / "demo" / "project.md").read_text(encoding="utf-8")
    assert scan_text(raw) == []
    assert TOKEN not in raw

    materialize_unknown_lenses(vault, project_ids=["demo"])
    path = vault / "generated" / "answers" / "ans-unknown-demo.json"
    written = path.read_text(encoding="utf-8")
    assert TOKEN not in written
    payload = json.loads(written)
    assert TOKEN not in json.dumps(payload, sort_keys=True)
    assert payload["signals"]["coverage_absent"] == []
    assert payload["signals"]["lifecycle"] == "unknown"


def test_unicode_escape_lifecycle_is_not_in_state_lens(tmp_path: Path) -> None:
    vault = _vault_with_escaped_semantic(tmp_path)
    raw = (vault / "projects" / "demo" / "project.md").read_text(encoding="utf-8")
    assert scan_text(raw) == []

    materialize_state_lenses(vault, project_ids=["demo"])
    path = vault / "generated" / "answers" / "ans-state-demo.json"
    written = path.read_text(encoding="utf-8")
    assert TOKEN not in written
    payload = json.loads(written)
    assert payload["lifecycle"] == "unknown"
    assert payload["rollup"] == "unknown"
    assert TOKEN not in str(payload["summary"])
    assert TOKEN not in str(payload["value"])


def test_clean_coverage_and_lifecycle_still_materialize(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    note = vault / "projects" / "demo" / "project.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "# demo\n\n"
        "## Semantic record\n"
        "```json\n"
        '{"coverage":[{"state":"absent","category":"auth-docs"}],'
        '"lifecycle":"active"}\n'
        "```\n",
        encoding="utf-8",
    )
    materialize_unknown_lenses(vault, project_ids=["demo"])
    unknown = json.loads(
        (vault / "generated" / "answers" / "ans-unknown-demo.json").read_text(
            encoding="utf-8"
        )
    )
    assert unknown["signals"]["coverage_absent"] == ["auth-docs"]
    assert unknown["signals"]["lifecycle"] == "active"
    assert TOKEN not in json.dumps(unknown, sort_keys=True)

    materialize_state_lenses(vault, project_ids=["demo"])
    state = json.loads(
        (vault / "generated" / "answers" / "ans-state-demo.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["lifecycle"] == "active"
    assert TOKEN not in json.dumps(state, sort_keys=True)
