"""D-193 foundation readiness rollup."""

from __future__ import annotations

from project_atlas.atlas3.foundation import REQUIRED_PULSE, foundation_readiness
from project_atlas.atlas3.pulse import PULSE_QUESTIONS
from project_atlas.atlas3.security import THREATS


def test_foundation_is_implementation_ready() -> None:
    report = foundation_readiness()
    assert report["foundation_implementation_ready"] is True
    assert report["chronicle_status"] == "ROADMAP_HORIZON"
    assert report["certified_surface_mutation"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"
    assert REQUIRED_PULSE.issubset(PULSE_QUESTIONS)
    assert "what_requires_attention" in PULSE_QUESTIONS
    assert len(THREATS) == 12
    assert all(report["checks"].values())
