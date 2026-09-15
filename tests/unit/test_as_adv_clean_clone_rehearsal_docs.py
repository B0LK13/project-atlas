"""Docs-as-spec checks for AS-ADV-CLEAN-CLONE-REHEARSAL-001."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "AS-ADV-CLEAN-CLONE-REHEARSAL.md"
HELPER = ROOT / "docs" / "scripts" / "adv_clean_clone_rehearsal.py"


def test_rehearsal_doc_keeps_all_authority_gates_closed() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "AS-ADV-CLEAN-CLONE-REHEARSAL-001" in text
    assert "AS-ADV-RELEASE-002" in text
    assert "clean_clone_replay" in text
    assert "RELEASE=NO" in text
    assert "PILOT=NO" in text
    assert "WEB ACCEPTED=NO" in text
    assert "Do not supply an estate path" in text


def test_rehearsal_helper_is_disposable_and_fail_closed() -> None:
    text = HELPER.read_text(encoding="utf-8")
    assert "TemporaryDirectory" in text
    assert 'CASE_ID = "clean_clone_replay"' in text
    assert '"release_certified"' in text
    assert '"estate_pilot_passed"' in text
    assert '"web_application_accepted"' in text
    assert 'print("RELEASE=NO")' in text
    assert "--report-vault" not in text
