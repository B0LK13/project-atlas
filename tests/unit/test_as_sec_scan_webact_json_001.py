"""AS-SEC-SCAN-WEBACT-JSON-001 — scan decoded JSON payload before ledger persist."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.authz import elevated_operator
from project_atlas.scaffold import create_scaffold
from project_atlas.secrets import scan_text
from project_atlas.web_actions import (
    WebActionError,
    _ledger_path,
    submit_web_action,
)

TOKEN = "bearer " + ("A" * 32)


def test_unicode_escape_payload_is_not_persisted(tmp_path: Path) -> None:
    raw = '{"q":"\\u0062earer ' + ("A" * 32) + '"}'
    assert scan_text(raw) == []
    body = json.loads(raw)
    assert body["q"] == TOKEN
    vault = tmp_path / "vault"
    create_scaffold(vault)
    with pytest.raises(WebActionError, match="web-action-secret-findings"):
        submit_web_action(
            vault,
            action_id="act-hunt",
            action_type="ask-query",
            payload=body,
            operator=elevated_operator("op", extra={"web.action"}),
        )
    assert not _ledger_path(vault).exists()


def test_nested_decoded_secret_is_not_persisted(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    create_scaffold(vault)
    with pytest.raises(WebActionError, match="web-action-secret-findings"):
        submit_web_action(
            vault,
            action_id="act-nest",
            action_type="ask-query",
            payload={"items": [{"q": TOKEN}]},
            operator=elevated_operator("op", extra={"web.action"}),
        )
    assert not _ledger_path(vault).exists()
