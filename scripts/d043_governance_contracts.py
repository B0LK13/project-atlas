"""Pure governance decision contracts for D-043 GE carrier reconciliation.

Measurement (git/gh/subprocess) lives elsewhere. These helpers encode the
production rules only — no I/O, no network, no hidden global state.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorklogAnalysisSummary:
    unrelated_historical_rewrite_count: int = 0
    encoding_only_rewrite_count: int = 0
    unexpected_changed_regions: int = 0
    encoding_regression_count: int = 0


@dataclass(frozen=True)
class CarrierDecision:
    case: str
    canonical_carrier: str
    pr607_disposition: str
    pr608_disposition: str
    pr609_disposition: str
    canonical_ge_carrier_ambiguity: int = 0


def expected_worklog_delta_only(analysis: WorklogAnalysisSummary) -> bool:
    """EXPECTED_WORKLOG_DELTA_ONLY = YES iff all unexpected rewrite counts are zero."""
    return (
        analysis.unrelated_historical_rewrite_count == 0
        and analysis.encoding_only_rewrite_count == 0
        and analysis.unexpected_changed_regions == 0
    )


def carrier_has_worklog_regression(analysis: WorklogAnalysisSummary) -> bool:
    """True when any carrier-owned rewrite introduces regression.

    A clean D-028 append or Lane C semantic equality cannot mask regression
    elsewhere — any non-zero regression signal fails the carrier.
    """
    return (
        analysis.encoding_regression_count > 0
        or analysis.unrelated_historical_rewrite_count > 0
        or analysis.encoding_only_rewrite_count > 0
        or analysis.unexpected_changed_regions > 0
    )


def closure_eligible(live_state: str, merged: bool = False) -> bool:
    """Pure closure-eligibility rule from supplied live-state data."""
    if merged:
        return False
    state = live_state.upper()
    if state in ("MERGED", "CLOSED"):
        return False
    if state == "OPEN":
        return True
    return False


def choose_canonical_carrier(
    pr608_worklog_regression: bool,
    pr609_worklog_regression: bool,
    ge_equivalent: bool,
    ci_equivalent: bool,
) -> CarrierDecision:
    """Pure carrier selection made before any loser supersession.

    Does not accept PR608_ALREADY_SUPERSEDED or other pre-decision inputs.
    """
    if (
        pr609_worklog_regression
        and not pr608_worklog_regression
        and ge_equivalent
        and ci_equivalent
    ):
        return CarrierDecision(
            case="C608",
            canonical_carrier="PR608_STACK",
            pr607_disposition="REQUIRED_BEFORE_CANONICAL_CARRIER",
            pr608_disposition="CANONICAL_AFTER_PR607",
            pr609_disposition="SUPERSEDED",
            canonical_ge_carrier_ambiguity=0,
        )
    if not pr609_worklog_regression:
        return CarrierDecision(
            case="C609",
            canonical_carrier="PR609",
            pr607_disposition="REQUIRED_SEPARATE_GOVERNANCE",
            pr608_disposition="SUPERSEDED_BY_PR609",
            pr609_disposition="CANONICAL",
            canonical_ge_carrier_ambiguity=0,
        )
    return CarrierDecision(
        case="C-AMBIGUOUS",
        canonical_carrier="AMBIGUOUS",
        pr607_disposition="UNKNOWN",
        pr608_disposition="UNKNOWN",
        pr609_disposition="UNKNOWN",
        canonical_ge_carrier_ambiguity=1,
    )


def worklog_summary_from_counts(
    *,
    unrelated_historical_rewrite_count: int = 0,
    encoding_only_rewrite_count: int = 0,
    unexpected_changed_regions: int = 0,
    encoding_regression_count: int = 0,
) -> WorklogAnalysisSummary:
    return WorklogAnalysisSummary(
        unrelated_historical_rewrite_count=unrelated_historical_rewrite_count,
        encoding_only_rewrite_count=encoding_only_rewrite_count,
        unexpected_changed_regions=unexpected_changed_regions,
        encoding_regression_count=encoding_regression_count,
    )
