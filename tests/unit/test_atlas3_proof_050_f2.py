"""AT3-050-F2 — blank evidence_ref is not independent proof."""

from __future__ import annotations

from pathlib import Path

from project_atlas.atlas3.proof import PROOF_STAGES, evaluate_proof


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def test_whitespace_evidence_ref_is_not_proven(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    report = evaluate_proof(
        vault,
        "AT3-050-BLANK",
        project_id="harbor-api",
        evidence={name: {"evidence_ref": "   "} for name in PROOF_STAGES},
        model_claims_complete=True,
    )
    assert report["chain_status"] == "UNPROVEN_MODEL_CLAIM"
    assert report["present_count"] == 0
    assert all(report["stages"][name]["status"] == "UNKNOWN" for name in PROOF_STAGES)
    assert report["model_claim_is_proof"] is False


def test_empty_evidence_ref_is_not_present(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    report = evaluate_proof(
        vault,
        "AT3-050-EMPTY",
        project_id="harbor-api",
        evidence={name: {"evidence_ref": ""} for name in PROOF_STAGES},
    )
    assert report["chain_status"] == "UNKNOWN"
    assert report["present_count"] == 0


def test_real_evidence_ref_still_proves(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    report = evaluate_proof(
        vault,
        "AT3-050-REAL",
        project_id="harbor-api",
        evidence={name: {"evidence_ref": f"ref-{name}"} for name in PROOF_STAGES},
    )
    assert report["chain_status"] == "PROVEN"
    assert report["present_count"] == len(PROOF_STAGES)
