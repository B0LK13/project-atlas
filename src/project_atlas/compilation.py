"""Per-source compilation outcome state machine (AS-EXT-001A, directive §7.8).

The outcome model makes per-file compilation status explicit so that one bad
source can no longer abort a whole batch silently: every source ends in a
terminal outcome with diagnostics and counters, and canonical promotion is
reachable only from :data:`CompilationOutcome.COMPLETE_CANDIDATE`.

Required flow::

    START
    → DISCOVERING
    → EXTRACTING
    → VALIDATING_CANDIDATE
    → COMPLETE_CANDIDATE / PARTIAL_CANDIDATE / FAILED
    → PROMOTING only from COMPLETE_CANDIDATE
    → COMPLETE or PROMOTION_FAILED

Guarantees encoded here (§7.8):

- ``PARTIAL_CANDIDATE`` may be written to staging/candidate output and must
  include diagnostics and counters; it may not alter canonical state, may not
  trigger lifecycle promotion, and may not appear as complete.
- ``FAILED`` means no promotable candidate exists.
- ``PROMOTION_FAILED`` leaves canonical state unchanged; the existing
  ingestion/OCC compare-and-swap contract and its tested rollback
  (AS-CORE-003, CORE3-023) remain authoritative — this module never performs
  promotion itself.

Promotion-phase mapping (§7.8, as wired in `project_atlas.ingestion`):

- ``state/compilation-outcomes/`` records the candidate phase, so a
  successfully promoted source persists as ``COMPLETE_CANDIDATE`` there;
  ``COMPLETE`` names the successful promotion phase itself and is implied
  by the promoted canonical transaction rather than duplicated into the
  candidate record.
- When the canonical transaction fails, promotable candidates are recorded
  as ``PROMOTION_FAILED`` in `quarantine/promotion-failures/index.json`
  (via the governed COMPLETE_CANDIDATE → PROMOTING → PROMOTION_FAILED
  edges) and a stale report is cleared on the next successful promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CompilationOutcome(StrEnum):
    """Per-source compilation states (directive §7.8)."""

    START = "START"
    DISCOVERING = "DISCOVERING"
    EXTRACTING = "EXTRACTING"
    VALIDATING_CANDIDATE = "VALIDATING_CANDIDATE"
    COMPLETE_CANDIDATE = "COMPLETE_CANDIDATE"
    PARTIAL_CANDIDATE = "PARTIAL_CANDIDATE"
    FAILED = "FAILED"
    PROMOTING = "PROMOTING"
    COMPLETE = "COMPLETE"
    PROMOTION_FAILED = "PROMOTION_FAILED"


#: Outcomes that end per-source processing. PARTIAL_CANDIDATE is terminal for
#: the candidate: it is staging-only and never re-enters promotion.
TERMINAL_OUTCOMES: frozenset[CompilationOutcome] = frozenset(
    {
        CompilationOutcome.COMPLETE,
        CompilationOutcome.PARTIAL_CANDIDATE,
        CompilationOutcome.FAILED,
        CompilationOutcome.PROMOTION_FAILED,
    }
)

_ALLOWED_TRANSITIONS: dict[CompilationOutcome, frozenset[CompilationOutcome]] = {
    CompilationOutcome.START: frozenset({CompilationOutcome.DISCOVERING}),
    CompilationOutcome.DISCOVERING: frozenset({CompilationOutcome.EXTRACTING}),
    CompilationOutcome.EXTRACTING: frozenset({CompilationOutcome.VALIDATING_CANDIDATE}),
    CompilationOutcome.VALIDATING_CANDIDATE: frozenset(
        {
            CompilationOutcome.COMPLETE_CANDIDATE,
            CompilationOutcome.PARTIAL_CANDIDATE,
            CompilationOutcome.FAILED,
        }
    ),
    CompilationOutcome.COMPLETE_CANDIDATE: frozenset({CompilationOutcome.PROMOTING}),
    CompilationOutcome.PARTIAL_CANDIDATE: frozenset(),
    CompilationOutcome.FAILED: frozenset(),
    CompilationOutcome.PROMOTING: frozenset(
        {CompilationOutcome.COMPLETE, CompilationOutcome.PROMOTION_FAILED}
    ),
    CompilationOutcome.COMPLETE: frozenset(),
    CompilationOutcome.PROMOTION_FAILED: frozenset(),
}


def compilation_transition_allowed(
    previous: CompilationOutcome, current: CompilationOutcome
) -> bool:
    """Return whether a compilation outcome edge is part of the §7.8 flow."""
    return current in _ALLOWED_TRANSITIONS[previous]


def validate_compilation_transition(
    previous: CompilationOutcome, current: CompilationOutcome
) -> None:
    """Raise a governed validation failure for an invalid outcome edge."""
    if not compilation_transition_allowed(previous, current):
        raise ValueError(
            f"invalid compilation outcome transition: {previous.value} -> {current.value}"
        )


def may_promote(outcome: CompilationOutcome) -> bool:
    """Return whether the outcome may enter canonical promotion (§7.8)."""
    return outcome is CompilationOutcome.COMPLETE_CANDIDATE


def alters_canonical_state(outcome: CompilationOutcome) -> bool:
    """Return whether reaching this outcome implies a canonical state change.

    Only a fully promoted candidate (COMPLETE) alters canonical state.
    PARTIAL_CANDIDATE, FAILED, and PROMOTION_FAILED must leave canonical
    state byte-identical.
    """
    return outcome is CompilationOutcome.COMPLETE


def triggers_lifecycle_promotion(outcome: CompilationOutcome) -> bool:
    """Return whether the outcome may trigger claim lifecycle promotion."""
    return outcome is CompilationOutcome.COMPLETE


def appears_complete(outcome: CompilationOutcome) -> bool:
    """Return whether the outcome may be reported as complete.

    PARTIAL_CANDIDATE must never be reported as complete (§7.8).
    """
    return outcome is CompilationOutcome.COMPLETE


@dataclass(frozen=True)
class CompilationCandidate:
    """Immutable per-source compilation result with counters and diagnostics.

    ``diagnostics`` carries structured, human-actionable entries; the full
    structured diagnostic model lands with directive §7.9 and reuses these
    fields. Counters reconcile extracted versus withheld claims so nothing
    drops silently. ``classification`` durably persists the §7.1
    classification record (sorted key/value pairs) per source.
    """

    source_path: str
    outcome: CompilationOutcome
    claims_extracted: int = 0
    claims_withheld: int = 0
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    classification: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.claims_extracted < 0 or self.claims_withheld < 0:
            raise ValueError("compilation counters must be non-negative")
        if self.outcome is CompilationOutcome.PARTIAL_CANDIDATE and not self.diagnostics:
            # A partial result without diagnostics is an invisible partial
            # success, which §7.8 forbids.
            raise ValueError("PARTIAL_CANDIDATE requires at least one diagnostic")
        if self.outcome is CompilationOutcome.COMPLETE_CANDIDATE and self.claims_withheld:
            raise ValueError("COMPLETE_CANDIDATE must not withhold claims")

    @property
    def promotable(self) -> bool:
        """Whether this candidate may enter canonical promotion."""
        return may_promote(self.outcome)

    @property
    def canonical_impact(self) -> str:
        """Coarse canonical-state impact for status reporting."""
        if self.outcome is CompilationOutcome.COMPLETE:
            return "promoted"
        return "none"
