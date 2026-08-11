import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from project_atlas.runtime_22 import compile_context

head = subprocess.check_output(
    ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
).strip()

results = {"head": head, "findings": {}}


def mini_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "generated" / "indexes").mkdir(parents=True)
    (vault / "state" / "claims").mkdir(parents=True)
    index = {
        "by_claim_id": {
            "claim-c": ["claim-c"],
            "claim-alpha": ["claim-alpha"],
            "claim-beta": ["claim-beta"],
        },
        "by_field": {},
        "by_concept_id": {},
        "by_source_lineage_id": {},
    }
    (vault / "generated" / "indexes" / "claims.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    claims = {
        "claims": [
            {
                "claim_id": "claim-c",
                "field": "status",
                "provenance": [{"ref": "sources/a.md"}],
            },
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
        json.dumps(claims, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    portfolio = vault / "generated" / "portfolio"
    portfolio.mkdir(parents=True)
    (portfolio / "stale-knowledge.json").write_text(
        json.dumps(
            {
                "sources": [
                    {"source_id": "a", "freshness": "stale"},
                    {"source_id": "b", "freshness": "fresh"},
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    conflicts = vault / "review" / "conflicts"
    conflicts.mkdir(parents=True)
    (conflicts / "conflicts.json").write_text(
        json.dumps(
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
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return vault


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    vault = mini_vault(root)

    pkg_launder = compile_context(
        vault,
        pack_id="adv005-001",
        profile_id="p2-readonly",
        candidates=[
            {
                "record_type": "claim",
                "record_id": "claim-c",
                "provenance": [
                    {"kind": "source", "ref": "sources/b.md"},
                    {"kind": "source", "ref": "sources/a.md"},
                ],
            }
        ],
    )
    fresh_001 = pkg_launder["entries"][0]["freshness"]
    results["findings"]["CLAUDE-ADV005-001"] = {
        "freshness_observed": fresh_001,
        "expected_if_correct": "stale",
        "laundered": fresh_001 == "fresh",
        "disposition": "REFUTED" if fresh_001 == "stale" else "REPRODUCED",
    }

    pkg_order_ab = compile_context(
        vault,
        pack_id="adv005-005-ab",
        profile_id="p2-readonly",
        candidates=[
            {
                "record_type": "claim",
                "record_id": "claim-c",
                "provenance": [
                    {"kind": "source", "ref": "sources/a.md"},
                    {"kind": "source", "ref": "sources/b.md"},
                ],
            }
        ],
    )
    pkg_order_ba = compile_context(
        vault,
        pack_id="adv005-005-ba",
        profile_id="p2-readonly",
        candidates=[
            {
                "record_type": "claim",
                "record_id": "claim-c",
                "provenance": [
                    {"kind": "source", "ref": "sources/b.md"},
                    {"kind": "source", "ref": "sources/a.md"},
                ],
            }
        ],
    )
    f_ab = pkg_order_ab["entries"][0]["freshness"]
    f_ba = pkg_order_ba["entries"][0]["freshness"]
    order_dep = f_ab != f_ba
    results["findings"]["CLAUDE-ADV005-005"] = {
        "freshness_order_a_then_b": f_ab,
        "freshness_order_b_then_a": f_ba,
        "order_dependent": order_dep,
        "disposition": "REFUTED" if not order_dep and f_ab == "stale" else "REPRODUCED",
    }

    pkg_excl = compile_context(
        vault,
        pack_id="adv005-012",
        profile_id="p2-readonly",
        include_unresolved_conflicts=False,
        candidates=[
            {
                "record_type": "claim",
                "record_id": "claim-alpha",
                "provenance": [{"kind": "source", "ref": "sources/a.md"}],
            },
            {
                "record_type": "claim",
                "record_id": "claim-beta",
                "provenance": [{"kind": "source", "ref": "sources/b.md"}],
            },
        ],
    )
    receipt = pkg_excl.get("pipeline_receipt", {})
    silent_winner = (
        pkg_excl["entry_count"] == 1
        and pkg_excl["entries"][0]["record_id"] == "claim-beta"
        and receipt.get("conflicts_excluded") == 1
        and "excluded_conflicts_detail" not in receipt
        and "excluded_conflict_ids" not in receipt
    )
    results["findings"]["CLAUDE-ADV005-012"] = {
        "entry_ids": [e["record_id"] for e in pkg_excl["entries"]],
        "receipt_subset": {
            k: receipt.get(k)
            for k in (
                "conflicts_excluded",
                "unresolved_conflicts_retained",
                "excluded_conflict_ids",
                "excluded_conflicts_detail",
            )
        },
        "silent_winner": silent_winner,
        "disposition": "REFUTED" if not silent_winner else "REPRODUCED",
    }

out_dir = Path(__file__).resolve().parent
(out_dir / "probe-result.json").write_text(
    json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(results, indent=2, sort_keys=True))
