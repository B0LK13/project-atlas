"""AS-2.0-TEMPINT-001 — temporal project intelligence.

Compares two evidenced slices. Does not fabricate history.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_TEMPINT
from project_atlas.intelligence.derived_state import (
    DerivedFact,
    FactStatus,
    StateContext,
    synthesize_project_state,
)
from project_atlas.intelligence.normalize import group_key
from project_atlas.intelligence.timewin import parse_instant
from project_atlas.intelligence.types import (
    AssessableClaim,
    SourceObservation,
    ValidityWindowInput,
    coerce_claims,
)


class TemporalDeltaClass(StrEnum):
    STABLE = "stable"
    CHANGED = "changed"
    BECAME_UNKNOWN = "became-unknown"
    BECAME_CONTESTED = "became-contested"
    BECAME_STALE = "became-stale"
    APPEARED = "appeared"
    DISAPPEARED = "disappeared"


class TemporalReasonClass(StrEnum):
    VALID_TIME = "valid-time-change"
    OBSERVATION_TIME = "observation-time-change"
    SOURCE_DISAPPEARED = "source-disappearance"
    NEW_EVIDENCE = "new-evidence"
    NEW_CONTRADICTION = "new-contradiction"
    SUCCESSION = "resolved-by-time-succession"
    UNKNOWN = "unknown"


class TemporalSlotDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delta_id: str
    subject: str
    field: str
    delta_class: TemporalDeltaClass
    reason_class: TemporalReasonClass
    reason: str
    earlier_status: str | None
    later_status: str | None
    earlier_value: str | None
    later_value: str | None


class TemporalProjectDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-TEMPINT-001"] = "AS-2.0-TEMPINT-001"
    report_id: str
    project_id: str
    earlier_as_of: str | None
    later_as_of: str | None
    slots: tuple[TemporalSlotDelta, ...]
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["temporal-not-fabricated"] = "temporal-not-fabricated"


def derive_temporal_intelligence(
    project_id: str,
    earlier_claims: Sequence[Claim | AssessableClaim],
    later_claims: Sequence[Claim | AssessableClaim],
    *,
    earlier_as_of: str | None = None,
    later_as_of: str | None = None,
    earlier_windows: tuple[ValidityWindowInput, ...] = (),
    later_windows: tuple[ValidityWindowInput, ...] = (),
    earlier_sources: tuple[SourceObservation, ...] | None = None,
    later_sources: tuple[SourceObservation, ...] | None = None,
) -> TemporalProjectDelta:
    """Diff two evidenced slices. Missing history stays unknown."""
    if not project_id.strip():
        raise ValueError("project_id is required")
    if earlier_as_of is not None:
        parse_instant(earlier_as_of, field="as-of")
    if later_as_of is not None:
        parse_instant(later_as_of, field="as-of")
    earlier_state = synthesize_project_state(
        project_id,
        earlier_claims,
        StateContext(
            as_of_valid_time=earlier_as_of,
            sources=earlier_sources,
            validity_windows=earlier_windows,
        ),
    )
    later_state = synthesize_project_state(
        project_id,
        later_claims,
        StateContext(
            as_of_valid_time=later_as_of,
            sources=later_sources,
            validity_windows=later_windows,
        ),
    )
    earlier_facts = _index_facts(
        earlier_state.known_facts
        + earlier_state.unknown_facts
        + earlier_state.stale_facts
        + earlier_state.contested_facts
    )
    later_facts = _index_facts(
        later_state.known_facts
        + later_state.unknown_facts
        + later_state.stale_facts
        + later_state.contested_facts
    )
    earlier_ids = {
        item.claim_id for item in coerce_claims(earlier_claims) if item.project_id == project_id
    }
    later_ids = {
        item.claim_id for item in coerce_claims(later_claims) if item.project_id == project_id
    }
    earlier_sources_present = _source_ids(earlier_sources)
    later_sources_present = _source_ids(later_sources)
    keys = sorted(set(earlier_facts) | set(later_facts))
    slots: list[TemporalSlotDelta] = []
    for key in keys:
        left = earlier_facts.get(key)
        right = later_facts.get(key)
        sample = left if left is not None else right
        if sample is None:
            continue
        subject, field = sample.subject, sample.field
        delta_class, reason_class, reason = _classify_slot(
            left,
            right,
            earlier_ids=earlier_ids,
            later_ids=later_ids,
            earlier_sources=earlier_sources_present,
            later_sources=later_sources_present,
            earlier_as_of=earlier_as_of,
            later_as_of=later_as_of,
        )
        material = "|".join((project_id, subject, field, delta_class.value, reason_class.value))
        slots.append(
            TemporalSlotDelta(
                delta_id="tmd-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
                subject=subject,
                field=field,
                delta_class=delta_class,
                reason_class=reason_class,
                reason=reason,
                earlier_status=left.status.value if left else None,
                later_status=right.status.value if right else None,
                earlier_value=left.value if left else None,
                later_value=right.value if right else None,
            )
        )
    slots.sort(key=lambda item: item.delta_id)
    slot_ids = ",".join(item.delta_id for item in slots)
    report_material = "|".join(
        (project_id, earlier_as_of or "", later_as_of or "", slot_ids)
    )
    return TemporalProjectDelta(
        report_id="tpr-" + hashlib.sha256(report_material.encode("utf-8")).hexdigest()[:20],
        project_id=project_id,
        earlier_as_of=earlier_as_of,
        later_as_of=later_as_of,
        slots=tuple(slots),
        truth_boundary=TRUTH_BOUNDARY_TEMPINT,
    )


def _index_facts(facts: tuple[DerivedFact, ...]) -> dict[str, DerivedFact]:
    indexed: dict[str, DerivedFact] = {}
    for item in facts:
        indexed[group_key(item.project_id, item.subject, item.field)] = item
    return indexed


def _source_ids(sources: tuple[SourceObservation, ...] | None) -> set[str] | None:
    if sources is None:
        return None
    return {item.source_id for item in sources if item.present and not item.deleted}


def _classify_slot(
    left: DerivedFact | None,
    right: DerivedFact | None,
    *,
    earlier_ids: set[str],
    later_ids: set[str],
    earlier_sources: set[str] | None,
    later_sources: set[str] | None,
    earlier_as_of: str | None,
    later_as_of: str | None,
) -> tuple[TemporalDeltaClass, TemporalReasonClass, str]:
    if left is None and right is not None:
        return (
            TemporalDeltaClass.APPEARED,
            TemporalReasonClass.NEW_EVIDENCE,
            "slot-appeared-in-later-slice",
        )
    if left is not None and right is None:
        if later_sources is not None and earlier_sources is not None:
            missing = earlier_sources - later_sources
            if missing:
                return (
                    TemporalDeltaClass.DISAPPEARED,
                    TemporalReasonClass.SOURCE_DISAPPEARED,
                    "source-disappeared-from-later-slice",
                )
        return (
            TemporalDeltaClass.DISAPPEARED,
            TemporalReasonClass.OBSERVATION_TIME,
            "slot-absent-from-later-slice",
        )
    assert left is not None and right is not None
    if (
        left.status is FactStatus.CONTESTED
        and right.status is not FactStatus.CONTESTED
        and earlier_as_of
        and later_as_of
    ):
        return (
            TemporalDeltaClass.CHANGED,
            TemporalReasonClass.SUCCESSION,
            "contested-resolved-by-time-succession",
        )
    if right.status is FactStatus.CONTESTED and left.status is not FactStatus.CONTESTED:
        return (
            TemporalDeltaClass.BECAME_CONTESTED,
            TemporalReasonClass.NEW_CONTRADICTION,
            "later-slice-is-contested",
        )
    if right.status is FactStatus.STALE and left.status is not FactStatus.STALE:
        return (
            TemporalDeltaClass.BECAME_STALE,
            TemporalReasonClass.VALID_TIME,
            "later-slice-is-stale-not-invalid",
        )
    if right.status is FactStatus.UNKNOWN and left.status is not FactStatus.UNKNOWN:
        return (
            TemporalDeltaClass.BECAME_UNKNOWN,
            TemporalReasonClass.UNKNOWN,
            "later-slice-became-unknown",
        )
    if left.value == right.value and left.status is right.status:
        return (
            TemporalDeltaClass.STABLE,
            TemporalReasonClass.OBSERVATION_TIME,
            "slot-unchanged-across-slices",
        )
    if later_ids - earlier_ids:
        return (
            TemporalDeltaClass.CHANGED,
            TemporalReasonClass.NEW_EVIDENCE,
            "later-slice-has-new-claim-ids",
        )
    if earlier_as_of and later_as_of:
        return (
            TemporalDeltaClass.CHANGED,
            TemporalReasonClass.VALID_TIME,
            "valid-time-slice-changed",
        )
    return (
        TemporalDeltaClass.CHANGED,
        TemporalReasonClass.OBSERVATION_TIME,
        "observed-values-or-status-changed",
    )
