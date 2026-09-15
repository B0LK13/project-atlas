"""AS-SEC-SCAN-NFKC-001 — compatibility lookalikes must not hide secrets.

``scan_text`` matched ASCII ``bearer`` / ``api_key`` / ``AKIA`` only.
Fullwidth Latin, fullwidth ``=`` / ``_``, and ideographic space are
NFKC-equivalent to those ASCII forms, so a ChatGPT bridge export could
persist credential-shaped material with empty findings (NFR-004 / AT-014).

Distinct from AS-SEC-SCAN-CF-001 (Cf separator fold) and from missing
token-prefix detection. Cyrillic/Greek confusables are out of scope.

Synthetic token only. Findings remain metadata-only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.chatgpt_bridge import ChatgptBridgeError, bridge_chatgpt_export
from project_atlas.secrets import REDACTED_PLACEHOLDER, redact_text, scan_text

# Synthetic — never a live credential.
_SYNTH = "A" * 32
_AKIA = "AKIA0123456789ABCDEF"
# Fullwidth Latin / punctuation via codepoints so ruff RUF001 stays quiet.
# ASCII + U+FEE0 == fullwidth (U+FF01..U+FF5E).
_FW_BEARER = "".join(chr(ord(ch) + 0xFEE0) for ch in "bearer")
_FW_API_KEY = "".join(chr(ord(ch) + 0xFEE0) for ch in "api_key")
_FW_AKIA = "".join(chr(ord(ch) + 0xFEE0) for ch in "AKIA")
_FW_EQUALS = "\uff1d"


def test_plain_bearer_still_detected() -> None:
    findings = scan_text(f"Authorization: bearer {_SYNTH}")
    assert any(item.pattern == "bearer-token" for item in findings)
    dumped = json.dumps([item.__dict__ for item in findings], sort_keys=True)
    assert _SYNTH not in dumped


def test_fullwidth_bearer_is_detected() -> None:
    text = f"Authorization: {_FW_BEARER} {_SYNTH}"
    findings = scan_text(text)
    assert any(item.pattern == "bearer-token" for item in findings)
    dumped = json.dumps([item.__dict__ for item in findings], sort_keys=True)
    assert _SYNTH not in dumped
    assert _FW_BEARER not in dumped


def test_fullwidth_bearer_is_redacted() -> None:
    redacted = redact_text(f"Authorization: {_FW_BEARER} {_SYNTH}")
    assert _SYNTH not in redacted
    assert REDACTED_PLACEHOLDER in redacted


def test_fullwidth_api_key_assignment_is_detected() -> None:
    text = f"{_FW_API_KEY}={_SYNTH}"
    findings = scan_text(text)
    assert any(item.pattern == "api-key-assignment" for item in findings)
    dumped = json.dumps([item.__dict__ for item in findings], sort_keys=True)
    assert _SYNTH not in dumped


def test_fullwidth_equals_api_key_is_detected() -> None:
    text = f"api_key{_FW_EQUALS}{_SYNTH}"
    findings = scan_text(text)
    assert any(item.pattern == "api-key-assignment" for item in findings)


def test_fullwidth_akia_is_detected() -> None:
    text = f"{_FW_AKIA}0123456789ABCDEF"
    findings = scan_text(text)
    assert any(item.pattern == "cloud-access-key" for item in findings)
    dumped = json.dumps([item.__dict__ for item in findings], sort_keys=True)
    assert _AKIA not in dumped
    assert _FW_AKIA not in dumped


def test_ideographic_space_bearer_is_detected() -> None:
    text = f"Authorization: bearer\u3000{_SYNTH}"
    findings = scan_text(text)
    assert any(item.pattern == "bearer-token" for item in findings)


def test_chatgpt_bridge_rejects_fullwidth_bearer(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    export = tmp_path / "chatgpt.md"
    export.write_text(
        f"User: hi\nAssistant: Authorization: {_FW_BEARER} {_SYNTH}\n",
        encoding="utf-8",
    )
    with pytest.raises(ChatgptBridgeError, match="chatgpt-export-secret-findings"):
        bridge_chatgpt_export(vault, export, bridge_id="br-a")
    generated = vault / "generated"
    assert not generated.exists()
    for path in vault.rglob("*"):
        if path.is_file():
            assert _SYNTH not in path.read_text(encoding="utf-8")
