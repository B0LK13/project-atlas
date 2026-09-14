"""AS-ASK2-UNREADABLE-CONFLICTS-001 — corrupt conflict overlay ≠ known.

Ask Atlas 2 previously skipped unreadable ``review/conflicts/*.json`` and
treated the overlay as empty. An unresolved conflict then answered
``status=known`` with ``conflict_state=none``.

Corrupt or schema-invalid overlay files must not launder CONFLICT into
KNOWN. Missing ``review/conflicts`` remains absent (not corrupt).
Readable unresolved rows still surface as conflict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.ask2 import ask_atlas_2
from project_atlas.runtime_22 import (
    _load_unresolved_claim_conflicts,
    compile_context,
)
from project_atlas.schema import validate_record


def _wr(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _empty_indexes(vault: Path) -> None:
    indexes = vault / "generated" / "indexes"
    indexes.mkdir(parents=True, exist_ok=True)
    for name in (
        "sources.json",
        "claims.json",
        "concepts.json",
        "conflicts.json",
        "authority.json",
        "provenance.json",
    ):
        (indexes / name).write_text("{}\n", encoding="utf-8", newline="\n")


def _claims_vault(tmp_path: Path, *, with_conflict: bool = False) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    _empty_indexes(vault)
    _wr(
        vault / "generated" / "indexes" / "claims.json",
        {
            "by_claim_id": {
                "claim-alpha": ["claim-alpha"],
                "claim-beta": ["claim-beta"],
            },
            "by_field": {"status": ["claim-alpha"], "owner": ["claim-beta"]},
            "by_concept_id": {},
            "by_source_lineage_id": {},
        },
    )
    _wr(
        vault / "state" / "claims" / "claims.json",
        {
            "claims": [
                {
                    "claim_id": "claim-alpha",
                    "field": "status",
                    "project_id": "demo",
                    "provenance": [{"ref": "sources/a.md"}],
                },
                {
                    "claim_id": "claim-beta",
                    "field": "owner",
                    "project_id": "demo",
                    "provenance": [{"ref": "sources/b.md"}],
                },
            ]
        },
    )
    if with_conflict:
        _wr(
            vault / "review" / "conflicts" / "conflicts.json",
            {
                "entries": [
                    {
                        "conflict_id": "conflict-alpha-status",
                        "state": "unresolved",
                        "claim_ids": ["claim-alpha"],
                        "subject": "project",
                        "field": "status",
                    }
                ]
            },
        )
    return vault


def test_readable_conflict_stays_conflict(tmp_path: Path) -> None:
    vault = _claims_vault(tmp_path, with_conflict=True)
    answer = ask_atlas_2(
        vault, question="status", project_id="demo", kinds=("claim",)
    )
    validate_record(answer, "ask-atlas-2-answer")
    assert answer["status"] == "conflict"
    assert answer["CONFLICTS"]["unresolved_count"] == 1
    assert "conflicts-overlay-unreadable" not in answer["UNKNOWN"]["reasons"]


def test_absent_conflicts_dir_remains_known(tmp_path: Path) -> None:
    vault = _claims_vault(tmp_path, with_conflict=False)
    answer = ask_atlas_2(
        vault, question="status", project_id="demo", kinds=("claim",)
    )
    validate_record(answer, "ask-atlas-2-answer")
    assert answer["status"] == "known"
    assert answer["UNKNOWN"]["is_unknown"] is False


def test_broken_json_overlay_is_unknown_not_known(tmp_path: Path) -> None:
    vault = _claims_vault(tmp_path, with_conflict=True)
    (vault / "review" / "conflicts" / "conflicts.json").write_text(
        "{broken json", encoding="utf-8"
    )
    answer = ask_atlas_2(
        vault, question="status", project_id="demo", kinds=("claim",)
    )
    validate_record(answer, "ask-atlas-2-answer")
    assert answer["status"] == "unknown"
    assert answer["UNKNOWN"]["is_unknown"] is True
    assert "conflicts-overlay-unreadable" in answer["UNKNOWN"]["reasons"]
    assert answer["CONFLICTS"]["unresolved_count"] == 0
    alpha = next(e for e in answer["EVIDENCE"] if e["record_id"] == "claim-alpha")
    assert alpha["conflict_state"] == "none"
    assert answer["llm_authority"] is False
    assert answer["canonical_write"] is False


def test_malformed_entries_overlay_is_unknown_not_known(tmp_path: Path) -> None:
    vault = _claims_vault(tmp_path, with_conflict=True)
    (vault / "review" / "conflicts" / "conflicts.json").write_text(
        json.dumps({"entries": "not-a-list"}), encoding="utf-8"
    )
    answer = ask_atlas_2(
        vault, question="status", project_id="demo", kinds=("claim",)
    )
    validate_record(answer, "ask-atlas-2-answer")
    assert answer["status"] == "unknown"
    assert "conflicts-overlay-unreadable" in answer["UNKNOWN"]["reasons"]


def test_mixed_valid_plus_corrupt_stays_conflict(tmp_path: Path) -> None:
    vault = _claims_vault(tmp_path, with_conflict=True)
    (vault / "review" / "conflicts" / "other.json").write_text(
        "{broken", encoding="utf-8"
    )
    answer = ask_atlas_2(
        vault, question="status", project_id="demo", kinds=("claim",)
    )
    validate_record(answer, "ask-atlas-2-answer")
    assert answer["status"] == "conflict"
    assert answer["CONFLICTS"]["unresolved_count"] == 1
    maps, _records, integrity = _load_unresolved_claim_conflicts(vault)
    assert integrity == "unreadable"
    assert "claim-alpha" in maps


def test_compiler_receipt_marks_unreadable_overlay(tmp_path: Path) -> None:
    vault = _claims_vault(tmp_path, with_conflict=True)
    (vault / "review" / "conflicts" / "conflicts.json").write_text(
        "{broken json", encoding="utf-8"
    )
    package = compile_context(
        vault,
        pack_id="ask2-unreadable-overlay",
        candidates=[
            {
                "record_type": "claim",
                "record_id": "claim-alpha",
                "slot": "lexical",
                "provenance": [{"kind": "source", "ref": "sources/a.md"}],
            }
        ],
        project_id="demo",
        profile_id="p2-readonly",
    )
    validate_record(package, "runtime-context-compiler")
    assert package["pipeline_receipt"]["conflicts_overlay"] == "unreadable"
    assert package["entries"][0]["conflict_state"] == "none"
