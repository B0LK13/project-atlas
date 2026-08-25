"""AT3-030 Atlas Start."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.start import compile_start


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def test_start_requires_budget(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(Atlas3Error) as exc:
        compile_start(vault, "harbor-api", token_budget=0)
    assert exc.value.code == "TOKEN_BUDGET_REQUIRED"


def test_start_is_budgeted_and_not_rag(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    briefing = compile_start(
        vault, "harbor-api", token_budget=240, current_task="Prepare Pulse demo"
    )
    assert briefing["rag_dump"] is False
    assert briefing["token_budget"] == 240
    assert briefing["tokens_remaining"] >= 0
    assert briefing["sections"]["current_task"]["text"].startswith("Prepare Pulse")
    assert "UNKNOWN" in briefing["sections"]["current_verified_truth"]["text"]
    assert len(briefing["sections"]["project_identity"]["text"]) <= 240
