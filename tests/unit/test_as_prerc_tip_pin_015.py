"""AS-PRERC-TIP-PIN-015 release authority pin guards."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_DIR = ROOT / "docs" / "releases" / "1.0.0"
MAIN = "518bdef66b24e099b889d2165540a6ca756e8aa4"
TREE = "d0eaa64a216b3f8bf3d9a67857f1b13a7f8af41c"
DOCUMENTS = (
    "README.md",
    "CHECKLIST.md",
    "EVIDENCE-INDEX.md",
    "RECEIPT-TEMPLATE.md",
)


def test_prerc_documents_pin_post_106_authority_tip() -> None:
    for name in DOCUMENTS:
        text = (RELEASE_DIR / name).read_text(encoding="utf-8")
        assert MAIN in text, f"{name} does not pin authority MAIN"
        assert TREE in text, f"{name} does not pin authority TREE"
        assert "RELEASE CERTIFIED = NO" in text
        assert "RELEASE CERTIFIED = YES" not in text


def test_prerc_owner_gate_state_remains_non_certifying() -> None:
    combined = "\n".join(
        (RELEASE_DIR / name).read_text(encoding="utf-8") for name in DOCUMENTS
    )
    assert "WEB APPLICATION ACCEPTED = YES" in combined
    assert "FIXTURE-ONLY CERT UNDER OWNER WAIVER = YES" in combined
    assert "Authentic estate PILOT = NO" in combined
    assert "D-PROJECT-ATLAS-1.0-OWNER-GATES-PARALLEL-CLOSEOUT-001" in combined
