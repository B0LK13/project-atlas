"""AS-CORE-004: duplicate semantic-subject fail-closed with explicit accounting."""

from __future__ import annotations

from pathlib import Path

from project_atlas.domain.diagnostics import CanonicalImpact, DiagnosticCode
from project_atlas.knowledge_compiler import compile_knowledge

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64


def test_duplicate_subject_withholds_definitional_and_third_party_references(
    tmp_path: Path,
) -> None:
    """A/B define wp:AS-DUP-001; C references it; D (AS-SAFE-001) continues."""
    entries = [
        {
            "source_id": "source-dup-a",
            "path": "docs/work-packages/AS-DUP-001.md",
            "classification": "work-package",
            "source": "../../sources/imported-documents/source-dup-a.md",
            "sha256": HASH_A,
            "text": "# AS-DUP-001\nStatus: active\n",
        },
        {
            "source_id": "source-dup-b",
            "path": "docs/work-packages/AS-DUP-001-copy.md",
            "classification": "work-package",
            "source": "../../sources/imported-documents/source-dup-b.md",
            "sha256": HASH_B,
            "text": "# AS-DUP-001\nStatus: draft\n",
        },
        {
            "source_id": "source-dup-c",
            "path": "docs/evidence/as-dup-001-receipt.yaml",
            "classification": "validation",
            "source": "../../sources/imported-documents/source-dup-c.yaml",
            "sha256": HASH_C,
            "text": (
                "schema_version: 1\n"
                "receipt_type: atlas-core-receipt\n"
                "work_package: AS-DUP-001\n"
                "status: certified\n"
            ),
        },
        {
            "source_id": "source-safe-d",
            "path": "docs/work-packages/AS-SAFE-001.md",
            "classification": "work-package",
            "source": "../../sources/imported-documents/source-safe-d.md",
            "sha256": HASH_D,
            "text": "# AS-SAFE-001\nStatus: active\n",
        },
    ]
    bundle = compile_knowledge("project-atlas", entries, tmp_path)

    # Ambiguous subject fully withheld (A/B definitional + C reference).
    assert all(claim.subject != "wp:AS-DUP-001" for claim in bundle.claims)
    # Unrelated unambiguous subject continues.
    assert any(claim.subject == "wp:AS-SAFE-001" for claim in bundle.claims)

    dup_diags = [
        d
        for d in bundle.diagnostics
        if d.code is DiagnosticCode.AMBIGUOUS_IDENTITY and d.subject == "wp:AS-DUP-001"
    ]
    assert len(dup_diags) == 1
    diag = dup_diags[0]
    assert diag.canonical_impact is CanonicalImpact.STAGING_ONLY
    assert diag.continued is True
    reason = diag.reason
    assert "wp:AS-DUP-001 is ambiguous" in reason
    assert "source-dup-a" in reason and "source-dup-b" in reason
    assert "docs/work-packages/AS-DUP-001.md" in reason
    assert "docs/work-packages/AS-DUP-001-copy.md" in reason
    assert "ALL claims depending on this subject are withheld" in reason
    assert "total_claims_withheld=" in reason
    assert "unique_claim_ids_withheld=" in reason
    assert "affected_source_ids=" in reason
    # Third-party receipt source must appear in affected accounting.
    assert "source-dup-c" in reason
    assert diag.remediation is not None
    assert "Third-party" in diag.remediation or "third-party" in diag.remediation.lower()

    # No path/parse-order winner: both definitional owners listed, neither claim kept.
    safe_subjects = {claim.subject for claim in bundle.claims}
    assert "wp:AS-SAFE-001" in safe_subjects
    assert "wp:AS-DUP-001" not in safe_subjects
