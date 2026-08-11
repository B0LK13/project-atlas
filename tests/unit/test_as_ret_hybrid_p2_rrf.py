"""AS-RET Hybrid P2 — Lexical/BM25/RRF fusion tests (deterministic)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from project_atlas.hybrid_retrieval import (
    PACKAGE_ID,
    HybridRetrievalError,
    build_hybrid_retrieval_plan,
    build_hybrid_rrf_fusion,
    fusion_to_json,
)
from project_atlas.retrieval import VaultRetriever
from project_atlas.retrieval_fusion import bm25_rank, rrf_fuse, tokenize
from project_atlas.schema import available_schemas, validate_record


def _seed_vault(vault: Path) -> None:
    indexes = vault / "generated" / "indexes"
    indexes.mkdir(parents=True)
    concepts_index = {
        "by_concept_id": {
            "alpha-auth": ["alpha-auth"],
            "beta-token": ["beta-token"],
            "gamma-auth-token": ["gamma-auth-token"],
        },
        "by_type": {"capability": ["alpha-auth", "beta-token", "gamma-auth-token"]},
        "by_project_id": {"demo": ["alpha-auth", "beta-token", "gamma-auth-token"]},
        "by_tag": {"auth": ["alpha-auth", "gamma-auth-token"], "token": ["beta-token"]},
        "by_relationship_target": {},
    }
    (indexes / "concepts.json").write_text(
        json.dumps(concepts_index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    for name in (
        "sources.json",
        "claims.json",
        "conflicts.json",
        "authority.json",
        "provenance.json",
    ):
        (indexes / name).write_text("{}\n", encoding="utf-8", newline="\n")

    concepts_dir = vault / "state" / "concepts"
    concepts_dir.mkdir(parents=True)
    (concepts_dir / "demo.json").write_text(
        json.dumps(
            {
                "concepts": [
                    {
                        "concept_id": "alpha-auth",
                        "type": "capability",
                        "project_id": "demo",
                        "summary": "authentication gate policy",
                        "provenance": [{"source_lineage_id": "sline-a"}],
                    },
                    {
                        "concept_id": "beta-token",
                        "type": "capability",
                        "project_id": "demo",
                        "summary": "bearer token issuance",
                        "provenance": [{"source_lineage_id": "sline-b"}],
                    },
                    {
                        "concept_id": "gamma-auth-token",
                        "type": "capability",
                        "project_id": "demo",
                        "summary": "auth token rotation policy",
                        "provenance": [{"source_lineage_id": "sline-c"}],
                    },
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _vault_fingerprint(vault: Path) -> dict[str, tuple[bytes, int]]:
    return {
        path.relative_to(vault).as_posix(): (path.read_bytes(), os.stat(path).st_mtime_ns)
        for path in vault.rglob("*")
        if path.is_file()
    }


def test_tokenize_ascii_deterministic() -> None:
    assert tokenize("Auth-Token_v2") == ["auth", "token", "v2"]
    assert tokenize("") == []


def test_bm25_rank_empty_query_fails_closed() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        bm25_rank("   ", [("a", "alpha")])
    with pytest.raises(ValueError, match="non-empty"):
        bm25_rank("", [("a", "alpha")])


def test_bm25_rank_deterministic_order() -> None:
    corpus = [
        ("doc-b", "token bearer"),
        ("doc-a", "auth token policy"),
        ("doc-c", "unrelated"),
    ]
    first = bm25_rank("auth token", corpus)
    second = bm25_rank("auth token", corpus)
    assert first == second
    assert first[0][0] == "doc-a"
    assert all(score > 0 for _, score in first)


def test_rrf_fuse_prefers_multi_list_hits() -> None:
    fused = rrf_fuse(
        {
            "lexical_exact": ["only-lex", "both"],
            "bm25": ["both", "only-bm25"],
        }
    )
    assert fused[0][0] == "both"
    assert set(fused[0][2]) == {"bm25", "lexical_exact"}


def test_hybrid_rrf_fusion_lexical_bm25(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_vault(vault)

    report = build_hybrid_rrf_fusion(
        vault, kind="concept", value="auth token", mode="exact", cap=10
    )

    assert report["package_id"] == PACKAGE_ID
    assert report["artifact_kind"] == "hybrid-retrieval-rrf"
    assert report["semantic_enabled"] is False
    assert report["slots"]["semantic"]["enabled"] is False
    assert report["authority"]["level"] == "derived"
    assert report["authority"]["llm_authority"] is False
    assert report["fusion"]["method"] == "rrf"
    assert report["slots"]["bm25"]["status"] == "active"
    assert report["result_count"] == len(report["results"])
    assert report["results"]
    # Exact lexical key "auth token" will miss; BM25 should still surface docs.
    assert report["slots"]["lexical_exact"]["hit_count"] == 0
    assert report["slots"]["bm25"]["hit_count"] >= 1
    ids = [item["record_id"] for item in report["results"]]
    assert "gamma-auth-token" in ids
    assert all(item["authority_level"] == "derived" for item in report["results"])
    validate_record(report, "hybrid-retrieval-rrf")
    assert '"llm_authority": false' in fusion_to_json(report)


def test_hybrid_rrf_exact_lexical_boost(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_vault(vault)

    report = build_hybrid_rrf_fusion(
        vault, kind="concept", value="alpha-auth", mode="exact"
    )
    assert report["slots"]["lexical_exact"]["hit_count"] == 1
    assert report["results"][0]["record_id"] == "alpha-auth"
    assert "lexical_exact" in report["results"][0]["ranks"]


def test_hybrid_rrf_empty_query_fail_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_vault(vault)
    with pytest.raises(HybridRetrievalError, match="value-empty"):
        build_hybrid_rrf_fusion(vault, kind="concept", value="  ")
    with pytest.raises(HybridRetrievalError, match="value-empty"):
        build_hybrid_retrieval_plan(vault, kind="concept", value="")


def test_hybrid_rrf_rejects_semantic_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_vault(vault)
    with pytest.raises(HybridRetrievalError, match="semantic-slot-not-available"):
        build_hybrid_rrf_fusion(
            vault, kind="concept", value="auth", enable_semantic=True
        )


def test_hybrid_rrf_does_not_write_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_vault(vault)
    before = _vault_fingerprint(vault)
    build_hybrid_rrf_fusion(vault, kind="concept", value="token")
    assert _vault_fingerprint(vault) == before


def test_hybrid_rrf_repeat_run_byte_identical(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_vault(vault)
    a = fusion_to_json(build_hybrid_rrf_fusion(vault, kind="concept", value="auth"))
    b = fusion_to_json(build_hybrid_rrf_fusion(vault, kind="concept", value="auth"))
    assert a == b


def test_vault_retriever_bm25_corpus_sorted(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_vault(vault)
    corpus = VaultRetriever(vault).bm25_corpus("concept")
    ids = [record_id for record_id, _text in corpus]
    assert ids == sorted(ids)
    assert all("alpha-auth" in text or record_id != "alpha-auth" for record_id, text in corpus)


def test_hybrid_rrf_schema_registered() -> None:
    assert "hybrid-retrieval-rrf" in available_schemas()
    assert "hybrid-retrieval-plan" in available_schemas()
