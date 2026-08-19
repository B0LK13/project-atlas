"""Adversarial review trigger for high-risk control-plane work."""

from __future__ import annotations

from project_atlas.orchestration.autonomy.models import RiskTag

ADVERSARIAL_TRIGGERS: frozenset[RiskTag] = frozenset(RiskTag)


def requires_adversarial_review(tags: tuple[RiskTag, ...]) -> bool:
    return any(tag in ADVERSARIAL_TRIGGERS for tag in tags)
