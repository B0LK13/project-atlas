"""AS-2.0-CHANGE-001 — semantic change intelligence.

Change is not regression. Only evidenced predecessor, update, or
temporal succession is reported.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim, ClaimLifecycle
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_CHANGE
from project_atlas.intelligence.normalize import group_key, normalize_value
from project_atlas.intelligence.timewin import windows_relation
from project_atlas.intelligence.types import (
    AssessableClaim,
    ValidityWindowInput,
    coerce_claims,
)


class ChangeClass(StrEnum):
    PREDECESSOR = "predecessor"
    UPDATED = "updated"
    SUCCESSION = "succession"
    UNKNOWN = "unknown"


class SemanticChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-CHANGE-001"] = "AS-2.0-CHANGE-001"
    change_id: str
    project_id: str | None
    subject: str
    field: str
    change_class: ChangeClass
    from_claim_id: str | None
    to_claim_id: str
    from_value: str | None
    to_value: str
    reason: str
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["change-not-regression"] = "change-not-regression"


def detect_semantic_changes(
    claims: Sequence[Claim | AssessableClaim],
    *,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
) -> tuple[SemanticChange, ...]:
    items = coerce_claims(claims)
    by_id = {item.claim_id: item for item in items}
    windows = {item.claim_id: item for item in validity_windows}
    groups: dict[str, list[AssessableClaim]] = {}
    for item in items:
        groups.setdefault(group_key(item.project_id, item.subject, item.field), []).append(item)
    found: list[SemanticChange] = []
    for bucket in groups.values():
        bucket.sort(key=lambda item: item.claim_id)
        for item in bucket:
            if item.predecessor_claim_id and item.predecessor_claim_id in by_id:
                prior = by_id[item.predecessor_claim_id]
                found.append(
                    _change(
                        item,
                        ChangeClass.PREDECESSOR,
                        prior.claim_id,
                        prior.value,
                        "predecessor-claim-id-evidenced",
                    )
                )
            elif item.lifecycle is ClaimLifecycle.UPDATED:
                found.append(
                    _change(item, ChangeClass.UPDATED, None, None, "lifecycle-updated")
                )
        for index, left in enumerate(bucket):
            for right in bucket[index + 1 :]:
                left_window = windows.get(left.claim_id)
                right_window = windows.get(right.claim_id)
                if left_window is None or right_window is None:
                    continue
                if (
                    windows_relation(
                        left_window.valid_from,
                        left_window.valid_to,
                        right_window.valid_from,
                        right_window.valid_to,
                    )
                    != "succession"
                ):
                    continue
                if normalize_value(left.value, left.normalized_text) == normalize_value(
                    right.value, right.normalized_text
                ):
                    continue
                right_start = right_window.valid_from or ""
                left_start = left_window.valid_from or ""
                later = right if right_start >= left_start else left
                earlier = left if later is right else right
                found.append(
                    _change(
                        later,
                        ChangeClass.SUCCESSION,
                        earlier.claim_id,
                        earlier.value,
                        "temporally-disjoint-successor",
                    )
                )
    found.sort(key=lambda item: item.change_id)
    return tuple(found)


def _change(
    item: AssessableClaim,
    change_class: ChangeClass,
    from_claim_id: str | None,
    from_value: str | None,
    reason: str,
) -> SemanticChange:
    material = "|".join(
        (
            item.project_id or "",
            item.subject,
            item.field,
            change_class.value,
            from_claim_id or "",
            item.claim_id,
        )
    )
    return SemanticChange(
        change_id="chg-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        project_id=item.project_id,
        subject=item.subject,
        field=item.field,
        change_class=change_class,
        from_claim_id=from_claim_id,
        to_claim_id=item.claim_id,
        from_value=from_value,
        to_value=item.value,
        reason=reason,
        truth_boundary=TRUTH_BOUNDARY_CHANGE,
    )
