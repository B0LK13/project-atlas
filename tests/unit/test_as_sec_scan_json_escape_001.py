"""AS-SEC-SCAN-JSON-ESC-001 — decoded JSON turns must be scanned.

``chatgpt_bridge`` / ``import_openai_export`` scanned the raw export only.
A JSON ``\\u0062earer`` escape does not match ``\\bbearer\\s+``, but
``parse_chat_export`` decodes it to ASCII ``bearer`` + token and persists
the decoded turn (NFR-004 / AT-014).

Distinct from AS-SEC-SCAN-NFKC-001 (compatibility lookalikes) and
AS-SEC-SCAN-CF-001 (Cf separators). Synthetic token only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.chatgpt_bridge import ChatgptBridgeError, bridge_chatgpt_export
from project_atlas.openai_import_real import OpenAIRealImportError, import_openai_export
from project_atlas.openai_importer_fixtures import parse_chat_export
from project_atlas.secrets import scan_text

# Synthetic — never a live credential.
_SYNTH = "A" * 32
# Literal backslash-u escape of the leading ``b`` in bearer.
_ESCAPED_JSON = (
    '[{"role":"assistant","content":"Authorization: \\u0062earer ' + _SYNTH + '"}]'
)


def test_raw_json_escape_misses_and_decode_hits() -> None:
    assert "bearer" not in _ESCAPED_JSON
    assert scan_text(_ESCAPED_JSON) == []
    turns = parse_chat_export(_ESCAPED_JSON)
    assert turns[0].text.startswith("Authorization: bearer ")
    assert any(item.pattern == "bearer-token" for item in scan_text(turns[0].text))


def test_chatgpt_bridge_rejects_json_escaped_bearer(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    export = tmp_path / "chatgpt.json"
    export.write_text(_ESCAPED_JSON, encoding="utf-8")
    with pytest.raises(ChatgptBridgeError, match="chatgpt-export-secret-findings"):
        bridge_chatgpt_export(vault, export, bridge_id="br-esc")
    assert not (vault / "generated").exists()
    for path in vault.rglob("*"):
        if path.is_file():
            assert _SYNTH not in path.read_text(encoding="utf-8")


def test_openai_import_rejects_json_escaped_bearer(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    export = tmp_path / "chatgpt.json"
    export.write_text(_ESCAPED_JSON, encoding="utf-8")
    with pytest.raises(OpenAIRealImportError, match="oai-export-secret-findings"):
        import_openai_export(vault, export, import_id="imp-esc")
    assert not (vault / "generated").exists()
    for path in vault.rglob("*"):
        if path.is_file():
            assert _SYNTH not in path.read_text(encoding="utf-8")


def test_plain_markdown_bearer_still_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    export = tmp_path / "chatgpt.md"
    export.write_text(
        f"User: hi\nAssistant: Authorization: bearer {_SYNTH}\n",
        encoding="utf-8",
    )
    with pytest.raises(ChatgptBridgeError, match="chatgpt-export-secret-findings"):
        bridge_chatgpt_export(vault, export, bridge_id="br-md")
    assert not (vault / "generated").exists()
