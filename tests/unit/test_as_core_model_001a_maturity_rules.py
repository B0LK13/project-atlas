"""AS-CORE-MODEL-001A — deterministic project-concept maturity fill."""

from __future__ import annotations

import pytest

from project_atlas.domain import Maturity
from project_atlas.knowledge_compiler import derive_project_maturity


def _entry(classification: str, *, maturity: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_id": f"source-{classification}",
        "path": f"docs/{classification}.md",
        "classification": classification,
        "text": f"# {classification}\n",
    }
    if maturity is not None:
        payload["maturity"] = maturity
    return payload


def test_rule_a_declared_marker_wins_over_empty_coverage() -> None:
    assert (
        derive_project_maturity(
            declared_maturity="mvp",
            open_conflicts=0,
            entries=[],
        )
        is Maturity.MVP
    )


def test_rule_a_invalid_declaration_fails_closed() -> None:
    with pytest.raises(ValueError, match="invalid project maturity declaration"):
        derive_project_maturity(
            declared_maturity="mostly-done",
            open_conflicts=0,
            entries=[],
        )


def test_rule_b_open_conflicts_without_declaration_yield_none() -> None:
    assert (
        derive_project_maturity(
            declared_maturity=None,
            open_conflicts=1,
            entries=[
                _entry("project-overview"),
                _entry("architecture"),
                _entry("security"),
                _entry("validation"),
            ],
        )
        is None
    )


def test_rule_c_required_plus_validation_is_beta() -> None:
    assert (
        derive_project_maturity(
            declared_maturity=None,
            open_conflicts=0,
            entries=[
                _entry("project-overview"),
                _entry("architecture"),
                _entry("security"),
                _entry("validation"),
            ],
        )
        is Maturity.BETA
    )


def test_rule_c_required_only_is_mvp() -> None:
    assert (
        derive_project_maturity(
            declared_maturity=None,
            open_conflicts=0,
            entries=[
                _entry("project-overview"),
                _entry("architecture"),
                _entry("security"),
            ],
        )
        is Maturity.MVP
    )


def test_rule_c_partial_non_required_coverage_is_prototype() -> None:
    assert (
        derive_project_maturity(
            declared_maturity=None,
            open_conflicts=0,
            entries=[_entry("project-overview")],
        )
        is Maturity.PROTOTYPE
    )


def test_rule_c_empty_coverage_is_none() -> None:
    assert (
        derive_project_maturity(
            declared_maturity=None,
            open_conflicts=0,
            entries=[],
        )
        is None
    )


def test_rule_d_ladder_never_auto_promotes_above_beta() -> None:
    # Even with rich coverage, ladder max is beta; production/hardened need Rule A.
    result = derive_project_maturity(
        declared_maturity=None,
        open_conflicts=0,
        entries=[
            _entry("project-overview"),
            _entry("architecture"),
            _entry("security"),
            _entry("validation"),
            _entry("readme"),
            _entry("runbook"),
        ],
    )
    assert result is Maturity.BETA
    assert result not in {
        Maturity.PRODUCTION_CANDIDATE,
        Maturity.PRODUCTION,
        Maturity.HARDENED,
    }


def test_rule_a_declaration_can_set_production() -> None:
    assert (
        derive_project_maturity(
            declared_maturity="production",
            open_conflicts=99,
            entries=[],
        )
        is Maturity.PRODUCTION
    )
