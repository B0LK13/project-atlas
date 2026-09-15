"""AS-SEC-CONT-001 — fixture continuous security gates.

Asserts secrets.scan_text metadata-only invariant and that the package
doc explicitly does not claim ESTATE PILOT / RELEASE. No Core mutation.
"""

from __future__ import annotations

from pathlib import Path

from project_atlas.secrets import SecretFinding, scan_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC = REPO_ROOT / "docs" / "AS-SEC-CONT-001-fixture-gates.md"

# Synthetic markers only — must never appear in findings metadata.
_FAKE_PASSWORD = "fixture-secret-password-value-001"
_FAKE_API_KEY = "fixture_api_key_ABCDEFGHIJKLMNOPQRST"
_FAKE_BEARER = "Bearer fixture.token.value.ABCDEFGHIJKLMNOPQRSTUV"


def test_scan_text_returns_metadata_only_findings() -> None:
    text = "\n".join(
        [
            f"password = '{_FAKE_PASSWORD}'",
            f"api_key = '{_FAKE_API_KEY}'",
            _FAKE_BEARER,
        ]
    )
    findings = scan_text(text)
    assert findings
    assert all(isinstance(item, SecretFinding) for item in findings)

    serialized = " ".join(
        f"{item.pattern}|{item.confidence}|{item.redacted_hint}" for item in findings
    )
    assert _FAKE_PASSWORD not in serialized
    assert _FAKE_API_KEY not in serialized
    assert "fixture.token.value" not in serialized
    assert all(item.redacted_hint == "content redacted" for item in findings)


def test_docs_exist_and_do_not_claim_pilot_or_release() -> None:
    assert DOC.is_file(), f"missing package doc: {DOC}"
    text = DOC.read_text(encoding="utf-8")
    assert "AS-SEC-CONT-001" in text
    assert "ESTATE PILOT" in text
    assert "RELEASE" in text
    assert "not claimed" in text.lower()
    # Soft negative: doc must not flip estate/release to yes.
    lowered = text.lower()
    assert "estate pilot passed** | **yes" not in lowered
    assert "release** | **yes" not in lowered
