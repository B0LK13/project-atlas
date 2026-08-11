"""AS-2.2-RUNTIME-001 — Hybrid Retrieval + Context Compiler P0 unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.runtime_22 import (
    PACKAGE_ID,
    Runtime22Error,
    compile_context,
    hybrid_retrieve,
)


def _mini_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "generated" / "indexes").mkdir(parents=True)
    (vault / "state" / "claims").mkdir(parents=True)
    index = {
        "by_claim_id": {"claim-alpha": ["claim-alpha"], "claim-beta": ["claim-beta"]},
        "by_field": {},
        "by_concept_id": {},
        "by_source_lineage_id": {},
    }
    (vault / "generated" / "indexes" / "claims.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    claims = {
        "claims": [
            {
                "claim_id": "claim-alpha",
                "field": "status",
                "provenance": [{"ref": "sources/a.md"}],
            },
            {
                "claim_id": "claim-beta",
                "field": "owner",
                "provenance": [{"ref": "sources/b.md"}],
            },
        ]
    }
    (vault / "state" / "claims" / "claims.json").write_text(
        json.dumps(claims, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return vault


def test_hybrid_retrieve_lexical_and_cap(tmp_path: Path) -> None:
    vault = _mini_vault(tmp_path)
    report = hybrid_retrieve(vault, kind="claim", value="claim-", mode="prefix", cap=1)
    assert report["package_id"] == PACKAGE_ID
    assert report["candidate_count"] == 1
    assert report["truncated"] is True
    assert report["slots"]["semantic"]["enabled"] is False
    assert report["authority"]["llm_authority"] is False
    assert report["candidates"][0]["authority_level"] == "derived"


def test_hybrid_retrieve_rejects_semantic(tmp_path: Path) -> None:
    vault = _mini_vault(tmp_path)
    with pytest.raises(Runtime22Error, match="semantic-slot-forbidden"):
        hybrid_retrieve(
            vault,
            kind="claim",
            value="claim-alpha",
            enable_semantic=True,
        )


def test_compile_context_budget_and_write(tmp_path: Path) -> None:
    vault = _mini_vault(tmp_path)
    hybrid = hybrid_retrieve(vault, kind="claim", value="claim-", mode="prefix", cap=20)
    package = compile_context(
        vault,
        pack_id="demo-pack",
        candidates=hybrid["candidates"],
        budget=1,
        write=True,
    )
    assert package["entry_count"] == 1
    assert package["truncated"] is True
    assert package["authority"]["estate_facts_invented"] is False
    out = vault / "generated" / "context-compiler" / "demo-pack-context-compiler.json"
    assert out.is_file()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["pack_id"] == "demo-pack"


def test_compile_context_unknown_profile(tmp_path: Path) -> None:
    vault = _mini_vault(tmp_path)
    with pytest.raises(Runtime22Error, match="profile-unknown"):
        compile_context(
            vault,
            pack_id="x",
            candidates=[],
            profile_id="invent-pilot",
        )


def test_compile_context_authority_spoof(tmp_path: Path) -> None:
    vault = _mini_vault(tmp_path)
    with pytest.raises(Runtime22Error, match="authority-spoof"):
        compile_context(
            vault,
            pack_id="x",
            candidates=[
                {
                    "record_type": "claim",
                    "record_id": "c1",
                    "authority_level": "canonical",
                }
            ],
        )
