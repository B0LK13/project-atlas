"""AS-ORCH-AUTONOMY-001 controlled in-process pilot against injected live inventory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main
from project_atlas.orchestration.autonomy.models import (
    EXPECTED_BASE_MAIN,
    EXPECTED_BASE_TREE,
    PILOT_PACKAGE_ID,
    LiveInventory,
)


@pytest.mark.integration
def test_pilot_exercises_real_governor_apis(tmp_path: Path) -> None:
    inventory = LiveInventory(
        current_main=EXPECTED_BASE_MAIN,
        current_tree=EXPECTED_BASE_TREE,
        worktree_status="CLEAN",
        open_relevant_prs=("396", "394"),
        active_successor_packages=(),
        r2_created="NO",
        r7_created="NO",
        authentic_r6_resumed="NO",
        as_orch_001e_started="NO",
        pr396_mutated="NO",
    )
    inv_path = tmp_path / "inventory.json"
    inv_path.write_text(inventory.model_dump_json(), encoding="utf-8")
    evidence = tmp_path / "evidence"
    code = main(
        [
            "orchestrator",
            "governor-pilot",
            "--root",
            str(tmp_path),
            "--inventory",
            str(inv_path),
            "--evidence-dir",
            str(evidence),
        ]
    )
    assert code == EXIT_OK
    bundle = json.loads((evidence / "pilot-evidence.json").read_text(encoding="utf-8"))
    assert bundle["bundle_kind"] == "PILOT_EXECUTION"
    assert bundle["payload"]["package_id"] == PILOT_PACKAGE_ID
    assert "generated.at" not in json.dumps(bundle)
