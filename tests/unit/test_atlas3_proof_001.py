"""AT3-050 agent proof-of-work."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.proof import PROOF_STAGES, evaluate_proof


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def test_model_claim_is_not_proof(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    report = evaluate_proof(
        vault,
        "AT3-050-DEMO",
        project_id="harbor-api",
        model_claims_complete=True,
    )
    assert report["model_claim_is_proof"] is False
    assert report["chain_status"] == "UNPROVEN_MODEL_CLAIM"
    assert report["merge_authorization"] == "NOT_GRANTED"
    assert all(report["stages"][name]["status"] == "UNKNOWN" for name in PROOF_STAGES)


def test_full_chain_is_proven_only_with_evidence(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    evidence = {name: {"evidence_ref": f"ref-{name}"} for name in PROOF_STAGES}
    report = evaluate_proof(
        vault,
        "AT3-050-FULL",
        project_id="harbor-api",
        evidence=evidence,
        model_claims_complete=True,
    )
    assert report["chain_status"] == "PROVEN"
    assert report["model_claim_is_proof"] is False


def test_string_evidence_is_invalid(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(Atlas3Error) as exc:
        evaluate_proof(
            vault,
            "AT3-050-STR",
            project_id="harbor-api",
            evidence="x",  # type: ignore[arg-type]
        )
    assert exc.value.code == "PROOF_EVIDENCE_INVALID"
    assert "evidence must be an object" in str(exc.value)


def test_list_evidence_is_invalid(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(Atlas3Error) as exc:
        evaluate_proof(
            vault,
            "AT3-050-LIST",
            project_id="harbor-api",
            evidence=[],  # type: ignore[arg-type]
        )
    assert exc.value.code == "PROOF_EVIDENCE_INVALID"
    assert "evidence must be an object" in str(exc.value)


def test_none_evidence_stays_unknown(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    report = evaluate_proof(
        vault,
        "AT3-050-NONE",
        project_id="harbor-api",
        evidence=None,
    )
    assert report["chain_status"] == "UNKNOWN"
    assert report["model_claim_is_proof"] is False
    assert all(report["stages"][name]["status"] == "UNKNOWN" for name in PROOF_STAGES)
