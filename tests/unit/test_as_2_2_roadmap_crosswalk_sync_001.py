"""AS-2.2-ROADMAP-CROSSWALK-SYNC-001 — docs sync only (no src mutation)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CW = ROOT / "docs" / "atlas-2.2" / "roadmap-crosswalk"
TIP = "5e2559f096ce6e1a906ee69ded45f8393ff2310b"
TREE = "2768267fa1923a3a1108f84fff9d77eae7e794fc"


def test_sync_card_and_crosswalk_mention_adv_pool_and_rollup() -> None:
    card = (CW / "AS-2.2-ROADMAP-CROSSWALK-SYNC-001.md").read_text(encoding="utf-8")
    cross = (CW / "CROSSWALK.md").read_text(encoding="utf-8")
    for text in (card, cross):
        assert "AS-2.2-ADV-POOL-001" in text or "ADV-POOL" in text
        assert "AS-2.2-PREP-FIXTURE-ROLLUP-001" in text or "FIXTURE-ROLLUP" in text
        assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert TIP in cross and TREE in cross
    assert "#243" in cross and "#242" in cross
    assert "#244" in cross and "#245" in cross
    assert "INDEX-013" in cross and "INDEX-014" in cross
    assert "Production mutation" in card and "NONE" in card
    assert "**NO**" in card


def test_fixture_tip_and_honesty_walls() -> None:
    data = json.loads((CW / "fixtures" / "crosswalk.fixture.json").read_text(encoding="utf-8"))
    assert data["tip_audited"] == TIP
    assert data["docs_atlas_2_2_tree"] == TREE
    assert data["sync_package_id"] == "AS-2.2-ROADMAP-CROSSWALK-SYNC-001"
    assert data["atlas_2_1_release_certified"] is False
    assert data["atlas_2_2_intelligence_unlocked"] is False
    assert data["pilot_roots"] == 0
    ids = {r["prep_package_id"] for r in data["rows"]}
    assert "AS-2.2-ADV-POOL-001" in ids
    assert "AS-2.2-PREP-FIXTURE-ROLLUP-001" in ids
    assert data["row_count"] == len(data["rows"])
