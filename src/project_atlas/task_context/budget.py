"""Tiered context budget. Mandatory content is never silently truncated."""

from __future__ import annotations

from project_atlas.task_context.models import (
    BudgetPartReport,
    BudgetReport,
    ContentTier,
    PacketFragment,
    TokenMeasureKind,
)

_TIER_ORDER = (ContentTier.BACKGROUND, ContentTier.EVIDENCE, ContentTier.MANDATORY)


def _estimate_tokens(chars: int) -> tuple[int | None, TokenMeasureKind]:
    """No tokenizer shipped: report a clearly labeled estimate (chars/4)."""
    return max(1, chars // 4) if chars else 0, TokenMeasureKind.ESTIMATED


def apply_budget(
    fragments: list[PacketFragment],
    *,
    budget_chars: int,
) -> tuple[list[PacketFragment], BudgetReport]:
    """Include fragments under budget. Drop background first, then evidence.

    If mandatory content cannot fit, mark incomplete_mandatory and keep
    mandatory fragments marked included=False with an overflow reason rather
    than silently shortening their bodies.
    """
    if budget_chars < 1:
        raise ValueError("budget_chars must be >= 1")

    # Stable order within tier: fragment_id.
    by_tier: dict[ContentTier, list[PacketFragment]] = {
        ContentTier.MANDATORY: [],
        ContentTier.EVIDENCE: [],
        ContentTier.BACKGROUND: [],
    }
    for frag in fragments:
        by_tier[frag.tier].append(frag)
    for tier in by_tier:
        by_tier[tier].sort(key=lambda item: item.fragment_id)

    selected: list[PacketFragment] = []
    deferred: list[PacketFragment] = []
    used = 0
    parts: list[BudgetPartReport] = []

    # Always attempt mandatory first.
    for frag in by_tier[ContentTier.MANDATORY]:
        tokens, measure = _estimate_tokens(frag.char_size)
        if used + frag.char_size <= budget_chars:
            selected.append(frag.model_copy(update={"included": True, "exclusion_reason": None}))
            used += frag.char_size
            parts.append(
                BudgetPartReport(
                    part_id=frag.fragment_id,
                    tier=frag.tier,
                    bytes=frag.byte_size,
                    chars=frag.char_size,
                    tokens=tokens,
                    token_measure=measure,
                    included=True,
                )
            )
        else:
            selected.append(
                frag.model_copy(
                    update={
                        "included": False,
                        "exclusion_reason": "budget-overflow-mandatory-not-silently-truncated",
                        "body": frag.body,  # retain full body in packet record for diagnosis
                    }
                )
            )
            parts.append(
                BudgetPartReport(
                    part_id=frag.fragment_id,
                    tier=frag.tier,
                    bytes=frag.byte_size,
                    chars=frag.char_size,
                    tokens=tokens,
                    token_measure=measure,
                    included=False,
                    exclusion_reason="budget-overflow-mandatory-not-silently-truncated",
                )
            )
            deferred.append(frag)

    incomplete_mandatory = any(
        not item.included and item.tier == ContentTier.MANDATORY for item in selected
    )

    # Then evidence, then background — only if mandatory fit.
    for tier in (ContentTier.EVIDENCE, ContentTier.BACKGROUND):
        for frag in by_tier[tier]:
            tokens, measure = _estimate_tokens(frag.char_size)
            # Pre-excluded (e.g. missing) stay excluded.
            if frag.included is False and frag.exclusion_reason:
                selected.append(frag)
                parts.append(
                    BudgetPartReport(
                        part_id=frag.fragment_id,
                        tier=frag.tier,
                        bytes=frag.byte_size,
                        chars=frag.char_size,
                        tokens=tokens,
                        token_measure=measure,
                        included=False,
                        exclusion_reason=frag.exclusion_reason,
                    )
                )
                continue
            if incomplete_mandatory or used + frag.char_size > budget_chars:
                reason = (
                    "budget-skipped-due-to-mandatory-overflow"
                    if incomplete_mandatory
                    else "budget-excluded-background-or-evidence"
                )
                selected.append(
                    frag.model_copy(update={"included": False, "exclusion_reason": reason})
                )
                parts.append(
                    BudgetPartReport(
                        part_id=frag.fragment_id,
                        tier=frag.tier,
                        bytes=frag.byte_size,
                        chars=frag.char_size,
                        tokens=tokens,
                        token_measure=measure,
                        included=False,
                        exclusion_reason=reason,
                    )
                )
            else:
                selected.append(
                    frag.model_copy(update={"included": True, "exclusion_reason": None})
                )
                used += frag.char_size
                parts.append(
                    BudgetPartReport(
                        part_id=frag.fragment_id,
                        tier=frag.tier,
                        bytes=frag.byte_size,
                        chars=frag.char_size,
                        tokens=tokens,
                        token_measure=measure,
                        included=True,
                    )
                )

    overflow_parts = tuple(
        part.part_id for part in parts if not part.included and part.exclusion_reason
        and "budget" in (part.exclusion_reason or "")
    )
    notes = [
        "token counts are ESTIMATED (chars/4); no tokenizer bundled",
        "packet budget does not bound runtime-loaded repo instructions or tool schemas",
        "no prompt-cache or cost savings claimed",
    ]
    if incomplete_mandatory:
        notes.append(
            "INCOMPLETE: mandatory requirements exceed budget; packet not fully deliverable"
        )

    report = BudgetReport(
        budget_chars=budget_chars,
        used_chars=used,
        remaining_chars=budget_chars - used,
        overflow=bool(overflow_parts) or incomplete_mandatory,
        incomplete_mandatory=incomplete_mandatory,
        overflow_parts=overflow_parts,
        parts=tuple(parts),
        notes=tuple(notes),
    )
    # Deterministic fragment order by id.
    selected.sort(key=lambda item: item.fragment_id)
    return selected, report
