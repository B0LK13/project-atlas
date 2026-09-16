"""AS-SEC-SCAN-READINESS-PROMOTE-LABEL-JSON-ESC-001 — decoded labels.

``readiness.promote`` reloads ``agent-readiness.yaml`` via
``yaml.safe_load`` and dumps the whole registry. A double-quoted YAML
``\\u0041KI…`` escape does not match ``scan_text`` on raw bytes, but
decode reveals ``AKIAAAAAAAAAAAAAAAAA`` (NFR-004 / AT-014).

Synthetic token only. Distinct from #827 (YAML constructor KeyError)
and listed P2 forged-grant/MAC class.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from agent_control import authority, readiness
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"


def test_promote_omits_json_escaped_foreign_label(tmp_path: Path) -> None:
    registry = tmp_path / "agent-readiness.yaml"
    planted = (
        "adapters:\n"
        "  other:\n"
        f'    label: "{ESC}"\n'
        "  generic-cli-v1: {}\n"
    )
    registry.write_text(planted, encoding="utf-8")
    raw = registry.read_text(encoding="utf-8")
    assert TOKEN not in raw
    assert scan_text(raw) == []
    loaded = yaml.safe_load(raw)
    assert loaded["adapters"]["other"]["label"] == TOKEN

    grant = {
        "grant_type": "atlas-authority-grant",
        "purpose": authority.PURPOSE_PROMOTE_READINESS,
        "grant_id": "grant-rdy-1",
        "subject": {
            "adapter_id": "generic-cli-v1",
            "skill_id": "atlas-governed-work",
            "skill_version": "1.0.0",
            "skill_sha256": "a" * 64,
        },
        "revoked": False,
    }
    result = readiness.promote(
        registry,
        "generic-cli-v1",
        "atlas-governed-work",
        "1.0.0",
        "a" * 64,
        "reh-1",
        "b" * 64,
        authority_grant=grant,
    )
    assert result["result"] == "promoted"
    written = registry.read_text(encoding="utf-8")
    assert TOKEN not in written
    assert scan_text(written) == []
    dumped = yaml.safe_load(written)
    assert dumped["adapters"]["other"]["label"] == "UNKNOWN"
    assert dumped["adapters"]["generic-cli-v1"]["governed_work_ready"] is True
