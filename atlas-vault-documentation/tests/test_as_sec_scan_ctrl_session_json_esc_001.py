"""AS-SEC-SCAN-CTRL-SESSION-JSON-ESC-001 — decoded session scalars must not persist.

``session.save`` rewrote ``.atlas/sessions/<id>.json`` after ``json.loads``
without rescanning decoded scalars. A JSON ``\\u0041KI…`` escape does not
match ``scan_text`` on raw bytes, but decode reveals
``AKIAAAAAAAAAAAAAAAAA`` (NFR-004 / AT-014).

Synthetic token only. Distinct from #988 (conversation-capture review
rewrite) and listed P2 session_capture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_control import session
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"


def test_json_unicode_escape_marker_is_not_persisted(tmp_path: Path) -> None:
    raw = '{"session":{"session_id":"s1"},"marker":"' + ESC + '"}'
    assert TOKEN not in raw
    assert scan_text(raw) == []
    state = json.loads(raw)
    assert state["marker"] == TOKEN
    assert any(finding.pattern == "cloud-access-key" for finding in scan_text(state["marker"]))

    with pytest.raises(ValueError, match="secret-shaped session state"):
        session.save(tmp_path, state)
    target = tmp_path / ".atlas" / "sessions" / "s1.json"
    assert not target.exists()


def test_safe_session_still_persists(tmp_path: Path) -> None:
    state = {"session": {"session_id": "s1"}, "marker": "control-fixture"}
    target = session.save(tmp_path, state)
    written = target.read_text(encoding="utf-8")
    assert TOKEN not in written
    assert scan_text(written) == []
    assert json.loads(written)["marker"] == "control-fixture"
