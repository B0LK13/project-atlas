"""AT3-030-F2 — Start must not present a stale state lens as current truth."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.start import compile_start


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_state(vault: Path, payload: object) -> None:
    answers = vault / "generated" / "answers"
    answers.mkdir(parents=True)
    (answers / "ans-state-harbor-api.json").write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )


def test_stale_verified_state_fails_closed_under_current(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_state(
        vault,
        {"freshness": "STALE", "status": "verified", "summary": "stale state presented as truth"},
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_start(
            vault,
            "harbor-api",
            token_budget=400,
            freshness_requirement="CURRENT",
        )
    assert exc.value.code == "STALE_AS_CURRENT"


def test_stale_state_fails_closed_even_without_verified_label(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_state(vault, {"freshness": "STALE", "summary": "historical state"})
    with pytest.raises(Atlas3Error) as exc:
        compile_start(
            vault,
            "harbor-api",
            token_budget=400,
            freshness_requirement="CURRENT",
        )
    assert exc.value.code == "STALE_AS_CURRENT"


def test_empty_state_object_stays_unknown(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_state(vault, {})
    briefing = compile_start(
        vault,
        "harbor-api",
        token_budget=400,
        freshness_requirement="CURRENT",
    )
    truth = briefing["sections"]["current_verified_truth"]
    assert truth["status"] == "UNKNOWN"
    assert "stale state presented as truth" not in truth["text"]
    assert briefing["stale_presented_as_current"] is False


def test_fresh_state_lens_still_derived(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_state(vault, {"status": "derived", "summary": "compose.yml changed"})
    briefing = compile_start(
        vault,
        "harbor-api",
        token_budget=400,
        freshness_requirement="CURRENT",
    )
    truth = briefing["sections"]["current_verified_truth"]
    assert truth["status"] == "derived"
    assert "compose.yml changed" in truth["text"]
    assert briefing["stale_presented_as_current"] is False
