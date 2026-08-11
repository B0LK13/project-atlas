"""Local remediation probe for CLAUDE-ADV005-009/013/019 (ADVANCE-005 Group C)."""

from __future__ import annotations

import inspect
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from project_atlas.hybrid_retrieval import (  # noqa: E402
    HybridRetrievalError,
    MAX_QUERY_CHARS,
    MAX_QUERY_TERMS,
    build_hybrid_retrieval_plan,
    build_hybrid_rrf_fusion,
)
from project_atlas.retrieval import VaultRetriever  # noqa: E402


def _seed_multi_project_vault(vault: Path) -> None:
    indexes = vault / "generated" / "indexes"
    indexes.mkdir(parents=True)
    concepts_index = {
        "by_concept_id": {
            "a-auth-gate": ["a-auth-gate"],
            "a-other": ["a-other"],
            "b-auth-gate": ["b-auth-gate"],
            "b-other": ["b-other"],
        },
        "by_type": {},
        "by_project_id": {
            "PROJECT_A": ["a-auth-gate", "a-other"],
            "PROJECT_B": ["b-auth-gate", "b-other"],
        },
        "by_tag": {},
        "by_relationship_target": {},
    }
    (indexes / "concepts.json").write_text(
        json.dumps(concepts_index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for name in (
        "sources.json",
        "claims.json",
        "conflicts.json",
        "authority.json",
        "provenance.json",
    ):
        (indexes / name).write_text("{}\n", encoding="utf-8")

    concepts_dir = vault / "state" / "concepts"
    concepts_dir.mkdir(parents=True)
    (concepts_dir / "PROJECT_A.json").write_text(
        json.dumps(
            {
                "concepts": [
                    {
                        "concept_id": "a-auth-gate",
                        "type": "capability",
                        "project_id": "PROJECT_A",
                        "summary": "secretmarker authentication gate",
                    },
                    {
                        "concept_id": "a-other",
                        "type": "capability",
                        "project_id": "PROJECT_A",
                        "summary": "PROJECT_A auxiliary",
                    },
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (concepts_dir / "PROJECT_B.json").write_text(
        json.dumps(
            {
                "concepts": [
                    {
                        "concept_id": "b-auth-gate",
                        "type": "capability",
                        "project_id": "PROJECT_B",
                        "summary": "secretmarker authentication gate",
                    },
                    {
                        "concept_id": "b-other",
                        "type": "capability",
                        "project_id": "PROJECT_B",
                        "summary": "PROJECT_B auxiliary",
                    },
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    rrf_params = list(
        inspect.signature(build_hybrid_rrf_fusion).parameters
    )
    results: dict[str, object] = {
        "009": {
            "api_has_project_id_param": "project_id" in rrf_params,
            "MAX_QUERY_CHARS": MAX_QUERY_CHARS,
            "MAX_QUERY_TERMS": MAX_QUERY_TERMS,
        }
    }

    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "vault"
        vault.mkdir()
        _seed_multi_project_vault(vault)

        shared = build_hybrid_rrf_fusion(
            vault,
            kind="concept",
            value="secretmarker authentication",
            project_id="PROJECT_A",
        )
        shared_ids = [item["record_id"] for item in shared["results"]]
        results["009"]["query_shared_token"] = {
            "result_ids": shared_ids,
            "PROJECT_B_present": "b-auth-gate" in shared_ids,
        }

        keyed = build_hybrid_rrf_fusion(
            vault, kind="concept", value="PROJECT_A", project_id="PROJECT_A"
        )
        keyed_ids = [item["record_id"] for item in keyed["results"]]
        results["009"]["query_project_a_key"] = {
            "result_ids": keyed_ids,
            "PROJECT_B_present": any(
                record_id.startswith("b-") for record_id in keyed_ids
            ),
        }
        results["009"]["bm25_corpus_size_scoped"] = len(
            VaultRetriever(vault).bm25_corpus("concept", project_id="PROJECT_A")
        )
        results["009"]["structural_isolation"] = not results["009"][
            "query_shared_token"
        ]["PROJECT_B_present"] and not results["009"]["query_project_a_key"][
            "PROJECT_B_present"
        ]

        repeat_query = "secretmarker " * 50000
        distinct_query = " ".join(f"term{n}" for n in range(300))
        cases: dict[str, object] = {}
        for label, query, expect in (
            ("repeat_50k", repeat_query, "query-too-long"),
            ("distinct_20k", distinct_query, "query-too-many-terms"),
        ):
            try:
                build_hybrid_rrf_fusion(
                    vault, kind="concept", value=query, project_id="PROJECT_A"
                )
                cases[label] = {"accepted": True, "error": None}
            except HybridRetrievalError as exc:
                cases[label] = {
                    "accepted": False,
                    "error": str(exc),
                    "matches": expect in str(exc),
                }
        results["013"] = {"cases": cases}

        empty = Path(tmp) / "empty"
        empty.mkdir()
        try:
            build_hybrid_rrf_fusion(
                empty, kind="concept", value="auth", project_id="demo"
            )
            missing_type = None
        except HybridRetrievalError as exc:
            missing_type = type(exc).__name__
        try:
            build_hybrid_retrieval_plan(
                empty, kind="concept", value="auth", project_id="demo"
            )
            plan_missing_type = None
        except HybridRetrievalError as exc:
            plan_missing_type = type(exc).__name__
        results["019"] = {
            "missing_indexes_type": missing_type,
            "plan_missing_indexes_type": plan_missing_type,
        }

    out = Path(__file__).parent / "probe-results.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))
    ok = (
        results["009"]["api_has_project_id_param"]
        and results["009"]["structural_isolation"]
        and all(not case["accepted"] for case in results["013"]["cases"].values())  # type: ignore[index]
        and results["019"]["missing_indexes_type"] == "HybridRetrievalError"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
