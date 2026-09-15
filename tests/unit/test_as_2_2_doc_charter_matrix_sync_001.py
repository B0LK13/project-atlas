"""AS-2.2-DOC-CHARTER-MATRIX-SYNC-001 — docs sync only."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "doc-charter"


def test_matrix_sync_lists_semidx_adv_rollup() -> None:
    text = (PREP / "FEATURE-MATURITY-MATRIX.md").read_text(encoding="utf-8")
    card = (PREP / "AS-2.2-DOC-CHARTER-MATRIX-SYNC-001.md").read_text(encoding="utf-8")
    for needle in (
        "AS-2.2-RET-SEMIDX-PREP-001",
        "AS-2.2-ADV-POOL-001",
        "AS-2.2-PREP-FIXTURE-ROLLUP-001",
        "AS-2.2-ROADMAP-CROSSWALK-SYNC-001",
    ):
        assert needle in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED" in text
    assert "**NO**" in card
    assert "Production mutation" in card and "NONE" in card


def test_matrix_fixture_includes_sync_packages() -> None:
    data = json.loads(
        (PREP / "fixtures" / "maturity-matrix.fixture.json").read_text(encoding="utf-8")
    )
    ids = {r["package_id"] for r in data["rows"]}
    assert "AS-2.2-RET-SEMIDX-PREP-001" in ids
    assert "AS-2.2-ADV-POOL-001" in ids
    assert data["row_count"] == len(data["rows"])
    assert data.get("atlas_2_1_release_certified") is False
