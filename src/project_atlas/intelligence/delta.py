"""AS-2.0-DELTA-001 — positive / negative delta classification.

Polarity is assigned only from explicit evidenced tokens. Version or
datastore succession is not an improvement. Unknown is not safe.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_DELTA
from project_atlas.intelligence.change import ChangeClass, SemanticChange, detect_semantic_changes
from project_atlas.intelligence.normalize import normalize_value
from project_atlas.intelligence.types import AssessableClaim, ValidityWindowInput

_POSITIVE_TOKENS = frozenset({"pass", "passed", "ok", "true"})
_NEGATIVE_TOKENS = frozenset({"fail", "failed", "false", "error"})


class DeltaPolarity(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"
    INCOMPARABLE = "incomparable"


class ValueDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-DELTA-001"] = "AS-2.0-DELTA-001"
    delta_id: str
    change_id: str
    polarity: DeltaPolarity
    reason: str
    from_value: str | None
    to_value: str
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["delta-not-score"] = "delta-not-score"


def classify_deltas(
    claims: Sequence[Claim | AssessableClaim],
    *,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
) -> tuple[ValueDelta, ...]:
    changes = detect_semantic_changes(claims, validity_windows=validity_windows)
    return tuple(_classify(item) for item in changes)


def _classify(change: SemanticChange) -> ValueDelta:
    polarity, reason = _polarity(change)
    material = "|".join((change.change_id, polarity.value, reason))
    return ValueDelta(
        delta_id="dlt-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        change_id=change.change_id,
        polarity=polarity,
        reason=reason,
        from_value=change.from_value,
        to_value=change.to_value,
        truth_boundary=TRUTH_BOUNDARY_DELTA,
    )


def _polarity(change: SemanticChange) -> tuple[DeltaPolarity, str]:
    if change.from_value is None:
        return DeltaPolarity.UNKNOWN, "no-from-value-to-compare"
    left = normalize_value(change.from_value)
    right = normalize_value(change.to_value)
    if left == right:
        return DeltaPolarity.NEUTRAL, "normalized-values-unchanged"
    if left in _NEGATIVE_TOKENS and right in _POSITIVE_TOKENS:
        return DeltaPolarity.POSITIVE, "explicit-fail-to-pass-token"
    if left in _POSITIVE_TOKENS and right in _NEGATIVE_TOKENS:
        return DeltaPolarity.NEGATIVE, "explicit-pass-to-fail-token"
    if change.change_class is ChangeClass.SUCCESSION:
        return DeltaPolarity.INCOMPARABLE, "temporal-succession-is-not-improvement"
    return DeltaPolarity.UNKNOWN, "values-differ-without-an-evidenced-polarity-rule"
