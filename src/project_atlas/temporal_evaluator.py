"""Current-state temporal evaluator (AS-CORE-005).

Claims stay immutable. This module derives dispositions and never uses
observation/mtime or generic latest-wins.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass

from project_atlas.domain.claims import Claim
from project_atlas.domain.conflicts import ConflictRecord, ConflictState
from project_atlas.domain.temporal import (
    CurrentStateRecord,
    ResolutionBasis,
    TemporalEvidenceKind,
    TemporalRelation,
    TemporalRelationKind,
    TemporalStatus,
)
from project_atlas.domain.vocabulary import AuthorityLevel
from project_atlas.temporal_evidence import ClaimTemporalContext, SourceTemporalFacts

_AUTHORITY_RANK: dict[str, int] = {
    AuthorityLevel.REJECTED.value: 0,
    AuthorityLevel.PENDING.value: 1,
    AuthorityLevel.INFERRED.value: 2,
    AuthorityLevel.GENERATED.value: 3,
    AuthorityLevel.MAINTAINED.value: 4,
    AuthorityLevel.VALIDATED_EXECUTION.value: 5,
    AuthorityLevel.PRIMARY.value: 6,
    AuthorityLevel.CONFLICTING.value: 0,
}

# Explicit lifecycle pairs (later, earlier) — not a global status ranking.
_LIFECYCLE_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("merged-and-post-merge-validated", "certified-merge-eligible"),
        ("merged-post-merge-validated", "certification-carry-forward-approved"),
        ("recertified-merge-eligible", "certified"),
    }
)

_CAND_TOKEN_RE = re.compile(r"V2-0*(\d+)", re.I)


@dataclass(frozen=True)
class TemporalEvaluation:
    """Result of evaluating one subject+field claim group."""

    disposition: CurrentStateRecord
    relations: tuple[TemporalRelation, ...]
    conflict_reclassified: bool


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]


def _authority_rank(value: str) -> int:
    return _AUTHORITY_RANK.get(value, 2)


def _candidate_num(token: str | None) -> int | None:
    if not token:
        return None
    match = _CAND_TOKEN_RE.search(token)
    return int(match.group(1)) if match else None


def _same_authority_or_unaffected(ctxs: list[ClaimTemporalContext]) -> bool:
    ranks = {_authority_rank(c.authority) for c in ctxs}
    return len(ranks) <= 1


def _graph_has_cycle(start: str, successors: dict[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in successors.get(node, ()):
            if dfs(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return dfs(start)


def _graph_reachable(start: str, successors: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(successors.get(node, ()))
    return seen


def _build_record(
    *,
    project_id: str | None,
    subject: str,
    field: str,
    status: TemporalStatus,
    basis: ResolutionBasis,
    current_id: str | None,
    historical: list[str],
    participating: list[str],
    rationale: str,
    compilation_id: str,
    authority_status: str,
) -> CurrentStateRecord:
    return CurrentStateRecord(
        project_id=project_id,
        subject=subject,
        field=field,
        temporal_status=status,
        resolution_basis=basis,
        current_claim_id=current_id,
        historical_claim_ids=tuple(sorted(set(historical))),
        participating_claim_ids=tuple(sorted(set(participating))),
        rationale=rationale,
        compilation_id=compilation_id,
        authority_status=authority_status,
    )


def _fail(
    ctxs: list[ClaimTemporalContext],
    *,
    project_id: str | None,
    compilation_id: str,
    status: TemporalStatus,
    basis: ResolutionBasis,
    rationale: str,
) -> TemporalEvaluation:
    subject = ctxs[0].subject
    field = ctxs[0].field
    ids = [c.claim_id for c in ctxs]
    return TemporalEvaluation(
        disposition=_build_record(
            project_id=project_id,
            subject=subject,
            field=field,
            status=status,
            basis=basis,
            current_id=None,
            historical=[],
            participating=ids,
            rationale=rationale,
            compilation_id=compilation_id,
            authority_status="blocked" if status is TemporalStatus.AUTHORITY_PENDING else "n/a",
        ),
        relations=(),
        conflict_reclassified=False,
    )


def _resolve_success(
    ctxs: list[ClaimTemporalContext],
    *,
    project_id: str | None,
    compilation_id: str,
    current: ClaimTemporalContext,
    historical: list[ClaimTemporalContext],
    basis: ResolutionBasis,
    rationale: str,
    relations: list[TemporalRelation],
) -> TemporalEvaluation:
    return TemporalEvaluation(
        disposition=_build_record(
            project_id=project_id,
            subject=current.subject,
            field=current.field,
            status=TemporalStatus.CURRENT,
            basis=basis,
            current_id=current.claim_id,
            historical=[c.claim_id for c in historical],
            participating=[c.claim_id for c in ctxs],
            rationale=rationale,
            compilation_id=compilation_id,
            authority_status="equivalent-or-unaffected",
        ),
        relations=tuple(relations),
        conflict_reclassified=True,
    )


def _try_lifecycle_pair(
    ctxs: list[ClaimTemporalContext],
    *,
    project_id: str | None,
    compilation_id: str,
) -> TemporalEvaluation | None:
    if len(ctxs) != 2:
        return None
    a, b = ctxs
    pair_ab = (a.value, b.value)
    pair_ba = (b.value, a.value)
    later: ClaimTemporalContext | None = None
    earlier: ClaimTemporalContext | None = None
    if pair_ab in _LIFECYCLE_PAIRS:
        later, earlier = a, b
    elif pair_ba in _LIFECYCLE_PAIRS:
        later, earlier = b, a
    else:
        return None
    # Require supporting evidence beyond the string pair.
    if later.value.startswith("merged") and not later.facts.has_post_merge_signal:
        return None
    if later.value == "recertified-merge-eligible" and not later.facts.original_certification:
        return None
    if not _same_authority_or_unaffected(ctxs) and _authority_rank(
        later.authority
    ) < _authority_rank(earlier.authority):
        return _fail(
            ctxs,
            project_id=project_id,
            compilation_id=compilation_id,
            status=TemporalStatus.AUTHORITY_PENDING,
            basis=ResolutionBasis.AUTHORITY_PENDING,
            rationale=(
                "lifecycle pair ordering is evidenced but later claim has "
                "lower authority; temporal selection withheld"
            ),
        )
    rel = TemporalRelation(
        kind=TemporalRelationKind.SUPERSEDES,
        from_claim_id=later.claim_id,
        to_claim_id=earlier.claim_id,
        evidence_kind=(
            TemporalEvidenceKind.SEMANTIC_EVENT
            if later.facts.merged_to_main_at or later.facts.original_certification
            else TemporalEvidenceKind.SOURCE_VERSION
        ),
        rationale=f"explicit lifecycle pair {earlier.value!r} -> {later.value!r}",
    )
    return _resolve_success(
        ctxs,
        project_id=project_id,
        compilation_id=compilation_id,
        current=later,
        historical=[earlier],
        basis=ResolutionBasis.LIFECYCLE_PAIR,
        rationale=rel.rationale,
        relations=[rel],
    )


def _try_candidate_supersession(
    ctxs: list[ClaimTemporalContext],
    *,
    project_id: str | None,
    compilation_id: str,
) -> TemporalEvaluation | None:
    """Resolve via candidate ordinals + supersedes tokens (CORE-003 style)."""
    with_ord = [c for c in ctxs if c.facts.candidate_ordinal is not None]
    if len(with_ord) < 2:
        return None
    # Build edges: higher ordinal supersedes lower when supersedes token mentions it
    # or when superseded_by / sequential supersedes chain is present.
    by_ord: dict[int, list[ClaimTemporalContext]] = defaultdict(list)
    for c in with_ord:
        assert c.facts.candidate_ordinal is not None
        by_ord[c.facts.candidate_ordinal].append(c)
    edges: list[tuple[ClaimTemporalContext, ClaimTemporalContext]] = []
    for ctx in with_ord:
        own = ctx.facts.candidate_ordinal
        assert own is not None
        mentioned = {_candidate_num(t) for t in ctx.facts.supersedes_tokens}
        mentioned.discard(None)
        for other_ord, others in by_ord.items():
            for other in others:
                if other.claim_id == ctx.claim_id:
                    continue
                # Explicit supersedes token mentioning another candidate in-group.
                # Direction: assertor is later (from). Mutual asserts → cycle later.
                if other_ord in mentioned:
                    edges.append((ctx, other))
                    continue
                # Soft adjacent only when supersedes present but tokens did not parse.
                if not mentioned and ctx.facts.supersedes_tokens and other_ord == own - 1:
                    edges.append((ctx, other))
        # superseded_by on older pointing to newer
        sb = _candidate_num(ctx.facts.superseded_by_token)
        if sb is not None and sb in by_ord and sb > own:
            for later in by_ord[sb]:
                edges.append((later, ctx))

    # Candidate supersession explains disagreeing stage labels. Same-value
    # ordinal carriers (e.g. work-package id reobservations) defer to
    # reobservation / plan-id handling.
    if len({c.value for c in with_ord}) <= 1:
        return None

    if not edges and len(with_ord) >= 2:
        # Require at least one supersedes token somewhere; do not rank by ordinal alone.
        if not any(c.facts.supersedes_tokens or c.facts.superseded_by_token for c in with_ord):
            return None
        # Soft chain: max ordinal current only if every lower has supersedes evidence path
        ordered = sorted(with_ord, key=lambda c: c.facts.candidate_ordinal or -1)
        current = ordered[-1]
        if not current.facts.supersedes_tokens and not any(
            _candidate_num(c.facts.superseded_by_token) == current.facts.candidate_ordinal
            for c in ordered[:-1]
        ):
            return None
        historical = ordered[:-1]
        relations = [
            TemporalRelation(
                kind=TemporalRelationKind.SUPERSEDES,
                from_claim_id=current.claim_id,
                to_claim_id=h.claim_id,
                evidence_kind=TemporalEvidenceKind.SOURCE_VERSION,
                rationale="candidate supersession chain",
            )
            for h in historical
        ]
        # Include non-candidate claims (e.g. Planned) as historical only if
        # document_timestamp precedes current candidate timestamp.
        extras = [c for c in ctxs if c.facts.candidate_ordinal is None]
        for extra in extras:
            planned_like = (
                extra.facts.status_value or ""
            ).lower() == "planned" or "amendment-plan" in extra.facts.path
            timed = (
                extra.facts.document_timestamp
                and current.facts.document_timestamp
                and extra.facts.document_timestamp <= current.facts.document_timestamp
            )
            non_candidate_residual = (
                extra.subject.startswith("wp:")
                and extra.subject == current.subject
                and extra.field == current.field
            )
            if planned_like or timed or non_candidate_residual:
                historical.append(extra)
                relations.append(
                    TemporalRelation(
                        kind=TemporalRelationKind.SUPERSEDES,
                        from_claim_id=current.claim_id,
                        to_claim_id=extra.claim_id,
                        evidence_kind=TemporalEvidenceKind.DOCUMENT_DECLARED,
                        rationale="planned/earlier residual vs candidate tip",
                    )
                )
            else:
                return _fail(
                    ctxs,
                    project_id=project_id,
                    compilation_id=compilation_id,
                    status=TemporalStatus.UNRESOLVED,
                    basis=ResolutionBasis.UNRESOLVED_AMBIGUOUS,
                    rationale=(
                        "candidate chain tip found but residual claims lack "
                        "comparable temporal evidence"
                    ),
                )
        if not _same_authority_or_unaffected([current, *historical]):
            return _fail(
                ctxs,
                project_id=project_id,
                compilation_id=compilation_id,
                status=TemporalStatus.AUTHORITY_PENDING,
                basis=ResolutionBasis.AUTHORITY_PENDING,
                rationale="candidate supersession blocked by authority inequality",
            )
        return _resolve_success(
            ctxs,
            project_id=project_id,
            compilation_id=compilation_id,
            current=current,
            historical=historical,
            basis=ResolutionBasis.SUPERSEDES,
            rationale="explicit candidate supersession chain",
            relations=relations,
        )

    # Graph tip: nodes with edges, no outgoing? "from supersedes to" means from=later
    successors: dict[str, set[str]] = defaultdict(set)
    predecessors: dict[str, set[str]] = defaultdict(set)
    for later, earlier in edges:
        successors[later.claim_id].add(earlier.claim_id)
        predecessors[earlier.claim_id].add(later.claim_id)
    tips = [c for c in with_ord if c.claim_id not in predecessors]
    if len(tips) != 1:
        basis = (
            ResolutionBasis.CYCLIC
            if len(tips) == 0 and edges
            else ResolutionBasis.BRANCHING
            if len(tips) > 1
            else ResolutionBasis.UNRESOLVED_AMBIGUOUS
        )
        return _fail(
            ctxs,
            project_id=project_id,
            compilation_id=compilation_id,
            status=TemporalStatus.UNRESOLVED,
            basis=basis,
            rationale=f"supersession graph has {len(tips)} tips; fail closed",
        )
    current = tips[0]
    # Detect cycles with a recursion stack (diamond ≠ cycle).
    if _graph_has_cycle(current.claim_id, successors):
        return _fail(
            ctxs,
            project_id=project_id,
            compilation_id=compilation_id,
            status=TemporalStatus.UNRESOLVED,
            basis=ResolutionBasis.CYCLIC,
            rationale="supersession cycle detected",
        )
    reachable = _graph_reachable(current.claim_id, successors)
    historical_ids = set(reachable) - {current.claim_id}
    historical = [c for c in ctxs if c.claim_id in historical_ids]
    # Unlinked claims remain unresolved unless reobservation of same value as current
    leftovers = [c for c in ctxs if c.claim_id not in reachable]
    for left in leftovers:
        if left.value == current.value:
            historical.append(left)
            continue
        planned_like = (
            left.facts.status_value or ""
        ).lower() == "planned" or "amendment-plan" in left.facts.path
        if planned_like:
            historical.append(left)
            continue
        if (
            left.facts.document_timestamp
            and current.facts.document_timestamp
            and left.facts.document_timestamp <= current.facts.document_timestamp
        ):
            historical.append(left)
            continue
        # Non-candidate residual on the same WP subject: earlier receipt /
        # remediation stages are historical once a unique candidate tip exists.
        # Competing candidates (with ordinals) stay fail-closed above.
        non_candidate_residual = (
            left.facts.candidate_ordinal is None
            and current.facts.candidate_ordinal is not None
            and left.subject.startswith("wp:")
            and left.subject == current.subject
            and left.field == current.field
        )
        if non_candidate_residual:
            historical.append(left)
            continue
        return _fail(
            ctxs,
            project_id=project_id,
            compilation_id=compilation_id,
            status=TemporalStatus.UNRESOLVED,
            basis=ResolutionBasis.UNRESOLVED_AMBIGUOUS,
            rationale="claims outside supersession graph remain incomparable",
        )
    relations = [
        TemporalRelation(
            kind=TemporalRelationKind.SUPERSEDES,
            from_claim_id=later.claim_id,
            to_claim_id=earlier.claim_id,
            evidence_kind=TemporalEvidenceKind.SOURCE_VERSION,
            rationale="candidate supersedes edge",
        )
        for later, earlier in edges
    ]
    return _resolve_success(
        ctxs,
        project_id=project_id,
        compilation_id=compilation_id,
        current=current,
        historical=historical,
        basis=ResolutionBasis.SUPERSEDES,
        rationale="supersession graph tip selected",
        relations=relations,
    )


def _try_remediation_chain(
    ctxs: list[ClaimTemporalContext],
    *,
    project_id: str | None,
    compilation_id: str,
) -> TemporalEvaluation | None:
    """AS-ID-001 style: prose supersedes + previous_implementation pointers."""
    if not any(c.facts.supersedes_prose or c.facts.previous_implementation for c in ctxs):
        return None
    if len({c.value for c in ctxs}) < 2:
        return None
    # Order by presence of previous_implementation chain depth heuristic:
    # claim that is never referenced as previous and has supersedes_prose or
    # previous_implementation is nearer tip; prefer one with previous_implementation
    # pointing at another source's commit mentioned in path? We only have facts.
    # Deterministic: sort by (has previous_impl, has supersedes_prose, claim_id)
    # Tip = the unique claim that has previous_implementation OR supersedes_prose
    # and whose value is not "earlier" stage words... Too fragile.
    #
    # Safer: build order from explicit supersedes_prose presence:
    # receipts with previous_implementation supersede those without when both
    # have package_status field and equal authority.
    # Score tip candidates: previous_implementation and supersedes_prose are
    # explicit remediation-chain evidence (AS-ID-001). Unique max score wins.
    scored: list[tuple[int, str, ClaimTemporalContext]] = []
    for c in ctxs:
        score = 0
        if c.facts.previous_implementation:
            score += 2
        if c.facts.supersedes_prose:
            score += 1
        scored.append((score, c.claim_id, c))
    scored.sort()
    if scored[-1][0] == 0:
        return None
    # Require unique max score
    max_score = scored[-1][0]
    tips = [c for s, _id, c in scored if s == max_score]
    if len(tips) != 1:
        return _fail(
            ctxs,
            project_id=project_id,
            compilation_id=compilation_id,
            status=TemporalStatus.UNRESOLVED,
            basis=ResolutionBasis.BRANCHING,
            rationale="remediation chain tip not unique",
        )
    current = tips[0]
    historical = [c for c in ctxs if c.claim_id != current.claim_id]
    if not _same_authority_or_unaffected(ctxs):
        return _fail(
            ctxs,
            project_id=project_id,
            compilation_id=compilation_id,
            status=TemporalStatus.AUTHORITY_PENDING,
            basis=ResolutionBasis.AUTHORITY_PENDING,
            rationale="remediation chain blocked by authority inequality",
        )
    relations = [
        TemporalRelation(
            kind=TemporalRelationKind.SUPERSEDES,
            from_claim_id=current.claim_id,
            to_claim_id=h.claim_id,
            evidence_kind=TemporalEvidenceKind.SOURCE_VERSION,
            rationale="remediation supersession / previous_implementation chain",
        )
        for h in historical
    ]
    return _resolve_success(
        ctxs,
        project_id=project_id,
        compilation_id=compilation_id,
        current=current,
        historical=historical,
        basis=ResolutionBasis.SUPERSEDES,
        rationale="remediation chain with explicit supersession evidence",
        relations=relations,
    )


def _try_reobservation_and_plan_id(
    ctxs: list[ClaimTemporalContext],
    *,
    project_id: str | None,
    compilation_id: str,
) -> TemporalEvaluation | None:
    """Duplicate same values + optional Planned amendment ID (CORE-003 work-package)."""
    by_value: dict[str, list[ClaimTemporalContext]] = defaultdict(list)
    for c in ctxs:
        by_value[c.value].append(c)
    if len(by_value) != 2:
        return None
    values = list(by_value.keys())
    major = max(values, key=lambda v: (len(by_value[v]), v))
    minor = next(v for v in values if v != major)
    if len(by_value[major]) < 2:
        return None
    # Minor is plan-like if any minor claim has status Planned or path amendment-plan
    minor_ctxs = by_value[minor]
    if not any(
        (c.facts.status_value or "").lower() == "planned"
        or "amendment-plan" in c.facts.path
        or (c.facts.work_package_value or "").endswith("-A")
        for c in minor_ctxs
    ):
        return None
    # Current: deterministic pick among major — reobservation; choose lexicographically
    # smallest claim_id as representative current (stable), others historical reobservations
    majors = sorted(by_value[major], key=lambda c: c.claim_id)
    current = majors[0]
    historical = majors[1:] + minor_ctxs
    relations = [
        TemporalRelation(
            kind=TemporalRelationKind.REOBSERVES,
            from_claim_id=current.claim_id,
            to_claim_id=h.claim_id,
            evidence_kind=TemporalEvidenceKind.UNKNOWN,
            rationale="duplicate observation of durable work-package id",
        )
        for h in majors[1:]
    ]
    relations.extend(
        TemporalRelation(
            kind=TemporalRelationKind.SUPERSEDES,
            from_claim_id=current.claim_id,
            to_claim_id=h.claim_id,
            evidence_kind=TemporalEvidenceKind.DOCUMENT_DECLARED,
            rationale="planned amendment id superseded by durable work-package id",
        )
        for h in minor_ctxs
    )
    return _resolve_success(
        ctxs,
        project_id=project_id,
        compilation_id=compilation_id,
        current=current,
        historical=historical,
        basis=ResolutionBasis.REOBSERVATION,
        rationale="durable WP id reobserved; planned amendment id historical",
        relations=relations,
    )


def evaluate_group(
    ctxs: list[ClaimTemporalContext],
    *,
    project_id: str | None,
    compilation_id: str,
) -> TemporalEvaluation:
    """Evaluate one same-subject/same-field group. Fail closed by default."""
    if len(ctxs) < 2:
        only = ctxs[0]
        return TemporalEvaluation(
            disposition=_build_record(
                project_id=project_id,
                subject=only.subject,
                field=only.field,
                status=TemporalStatus.CURRENT,
                basis=ResolutionBasis.REOBSERVATION,
                current_id=only.claim_id,
                historical=[],
                participating=[only.claim_id],
                rationale="single claim group",
                compilation_id=compilation_id,
                authority_status="equivalent-or-unaffected",
            ),
            relations=(),
            conflict_reclassified=False,
        )

    subject = ctxs[0].subject
    field = ctxs[0].field

    # Hard fail-closed: WP title collapse
    if field == "title" and subject.startswith("wp:"):
        return _fail(
            ctxs,
            project_id=project_id,
            compilation_id=compilation_id,
            status=TemporalStatus.AUTHORITY_PENDING,
            basis=ResolutionBasis.TITLE_COLLAPSE,
            rationale=(
                "multiple titles on a work-package subject; receipt document "
                "titles must not temporally supersede durable WP title "
                "(newest observation does not imply current truth)"
            ),
        )

    # Hard fail-closed: same source, incompatible values, no relation
    by_source: dict[str, list[ClaimTemporalContext]] = defaultdict(list)
    for c in ctxs:
        by_source[c.source_id].append(c)
    for _sid, group in by_source.items():
        values = {c.value for c in group}
        if len(values) > 1:
            return _fail(
                ctxs,
                project_id=project_id,
                compilation_id=compilation_id,
                status=TemporalStatus.UNRESOLVED,
                basis=ResolutionBasis.UNRESOLVED_SAME_SOURCE_MULTI,
                rationale=(
                    "same source yields incompatible values without temporal "
                    "relation (multi-row extraction collapse); coexist unresolved"
                ),
            )

    # Self-supersession / malformed
    for c in ctxs:
        own_ord = c.facts.candidate_ordinal
        for token in c.facts.supersedes_tokens:
            if own_ord is not None and _candidate_num(token) == own_ord:
                return _fail(
                    ctxs,
                    project_id=project_id,
                    compilation_id=compilation_id,
                    status=TemporalStatus.UNRESOLVED,
                    basis=ResolutionBasis.MALFORMED,
                    rationale="self-supersession token rejected",
                )

    for attempt in (
        _try_lifecycle_pair,
        _try_candidate_supersession,
        _try_remediation_chain,
        _try_reobservation_and_plan_id,
    ):
        result = attempt(ctxs, project_id=project_id, compilation_id=compilation_id)
        if result is not None:
            return result

    return _fail(
        ctxs,
        project_id=project_id,
        compilation_id=compilation_id,
        status=TemporalStatus.UNRESOLVED,
        basis=ResolutionBasis.UNRESOLVED_AMBIGUOUS,
        rationale="no explicit supersession or evidenced lifecycle pair; fail closed",
    )


def _contexts_for_claims(
    claims: list[Claim],
    facts_by_source: dict[str, SourceTemporalFacts],
) -> list[ClaimTemporalContext]:
    ctxs: list[ClaimTemporalContext] = []
    for claim in claims:
        sid = claim.provenance[0].source_id
        facts = facts_by_source.get(
            sid,
            SourceTemporalFacts(source_id=sid, path=claim.provenance[0].resource),
        )
        ctxs.append(
            ClaimTemporalContext(
                claim_id=claim.claim_id,
                subject=claim.subject,
                field=claim.field,
                value=claim.value,
                source_id=sid,
                authority=claim.authority.value,
                facts=facts,
                path=claim.provenance[0].resource,
            )
        )
    return ctxs


def evaluate_conflicts(
    claims: list[Claim],
    conflicts: list[ConflictRecord],
    facts_by_source: dict[str, SourceTemporalFacts],
    *,
    project_id: str | None,
    compilation_id: str,
) -> tuple[tuple[CurrentStateRecord, ...], tuple[TemporalRelation, ...], list[ConflictRecord]]:
    """Reclassify existing conflicts; claims remain immutable."""
    by_id = {claim.claim_id: claim for claim in claims}
    dispositions: list[CurrentStateRecord] = []
    relations: list[TemporalRelation] = []
    out_conflicts: list[ConflictRecord] = []

    for conflict in conflicts:
        group = [by_id[cid] for cid in conflict.claim_ids if cid in by_id]
        if len(group) < 2:
            out_conflicts.append(conflict)
            continue
        ctxs = _contexts_for_claims(group, facts_by_source)
        evaluation = evaluate_group(ctxs, project_id=project_id, compilation_id=compilation_id)
        dispositions.append(evaluation.disposition)
        relations.extend(evaluation.relations)
        if evaluation.conflict_reclassified:
            out_conflicts.append(
                conflict.model_copy(
                    update={
                        "state": ConflictState.RESOLVED,
                        "resolution": (
                            "historical-transition;"
                            f"current={evaluation.disposition.current_claim_id};"
                            f"basis={evaluation.disposition.resolution_basis.value}"
                        ),
                    }
                )
            )
        else:
            # Keep unresolved; stamp basis into resolution-null path via unchanged state
            out_conflicts.append(conflict)

    dispositions.sort(key=lambda d: (d.subject, d.field))
    relations.sort(key=lambda r: (r.from_claim_id, r.to_claim_id, r.kind.value))
    out_conflicts.sort(key=lambda c: c.conflict_id)
    return tuple(dispositions), tuple(relations), out_conflicts
