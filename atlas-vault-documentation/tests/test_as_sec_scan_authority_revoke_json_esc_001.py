"""AS-SEC-SCAN-AUTHORITY-REVOKE-JSON-ESC-001 — decoded grant scalars must not persist.

``revoke_grant`` reloads ``<store>/grants/<id>.json`` via ``json.loads``
and rewrites the grant. A JSON ``\\u0041KI…`` escape does not match
``scan_text`` on raw bytes, but decode reveals ``AKIAAAAAAAAAAAAAAAAA``
(NFR-004 / AT-014).

Synthetic token only. Distinct from #828 (malformed JSON fail-closed),
#893 (grant_id path confinement), and #992 (session.save).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_control import authority
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"


def test_revoke_refuses_json_escaped_issuer(tmp_path: Path) -> None:
    key = "k" * 32
    grant = authority.issue_grant(
        store=tmp_path,
        purpose=authority.PURPOSE_PROMOTE_READINESS,
        adapter_id="generic-cli-v1",
        skill_id="atlas-governed-work",
        skill_version="1.0.0",
        skill_sha256="a" * 64,
        issuer_id="owner",
        issuer_key=key,
    )
    path = tmp_path / "grants" / f"{grant['grant_id']}.json"
    grant["issuer_id"] = TOKEN
    grant["mac"] = authority.mac_for(grant, key.encode())
    grant["issuer_id"] = "PLACEHOLDER"
    planted = json.dumps(grant, indent=2, sort_keys=True).replace("PLACEHOLDER", ESC) + "\n"
    path.write_text(planted, encoding="utf-8")
    assert TOKEN not in planted
    assert scan_text(planted) == []
    assert json.loads(planted)["issuer_id"] == TOKEN

    with pytest.raises(ValueError, match="secret-shaped authority grant"):
        authority.revoke_grant(store=tmp_path, grant_id=grant["grant_id"], issuer_key=key)
    after = path.read_text(encoding="utf-8")
    assert TOKEN not in after
    assert scan_text(after) == []


def test_safe_revoke_still_persists(tmp_path: Path) -> None:
    key = "k" * 32
    grant = authority.issue_grant(
        store=tmp_path,
        purpose=authority.PURPOSE_PROMOTE_READINESS,
        adapter_id="generic-cli-v1",
        skill_id="atlas-governed-work",
        skill_version="1.0.0",
        skill_sha256="a" * 64,
        issuer_id="owner",
        issuer_key=key,
    )
    revoked = authority.revoke_grant(store=tmp_path, grant_id=grant["grant_id"], issuer_key=key)
    assert revoked["revoked"] is True
    path = tmp_path / "grants" / f"{grant['grant_id']}.json"
    written = path.read_text(encoding="utf-8")
    assert TOKEN not in written
    assert scan_text(written) == []
