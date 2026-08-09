"""AS-SEC-CONT-002 — deepen continuous security fixture gates.

Path-refuse + additional secrets metadata-only invariants. No Core mutation.
RELEASE / PILOT / WEB ACCEPTED remain unclaimed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.scaffold import ScaffoldError, validate_output_path
from project_atlas.secrets import SecretFinding, scan_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC = REPO_ROOT / "docs" / "AS-SEC-CONT-002-fixture-deepen.md"

_FAKE_PEM = "-----BEGIN RSA PRIVATE KEY-----\nfixture-pem-body-NOT-A-REAL-KEY\n-----END RSA PRIVATE KEY-----"
_FAKE_AKIA = "AKIAIOSFODNN7EXAMPLEXX"


def test_sec_cont_002_doc_exists_and_nonclaims() -> None:
    assert DOC.is_file()
    text = DOC.read_text(encoding="utf-8")
    assert "AS-SEC-CONT-002" in text
    assert "ESTATE PILOT PASSED" in text
    assert "**NO**" in text
    lowered = text.lower()
    assert "estate pilot passed** | **yes" not in lowered
    assert "release certified** | **yes" not in lowered


def test_validate_output_path_refuses_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "fake-home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    with pytest.raises(ScaffoldError, match="home directory"):
        validate_output_path(home)


def test_validate_output_path_refuses_nonempty_dir(tmp_path: Path) -> None:
    out = tmp_path / "nonempty"
    out.mkdir()
    (out / "noise.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ScaffoldError, match="not empty"):
        validate_output_path(out)


def test_private_key_and_akia_findings_are_metadata_only() -> None:
    text = f"{_FAKE_PEM}\naws_key={_FAKE_AKIA}\n"
    findings = scan_text(text)
    assert findings
    assert all(isinstance(item, SecretFinding) for item in findings)
    blob = " ".join(f"{item.pattern}|{item.confidence}|{item.redacted_hint}" for item in findings)
    assert "fixture-pem-body" not in blob
    assert _FAKE_AKIA not in blob
    assert all(item.redacted_hint == "content redacted" for item in findings)
    patterns = {item.pattern for item in findings}
    assert "private-key" in patterns or "cloud-access-key" in patterns
