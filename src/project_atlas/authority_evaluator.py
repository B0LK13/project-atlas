"""Domain-specific authority evaluation (AS-CORE-006).

Consumes AS-CORE-005 temporal dispositions. Never mutates claims or temporal
output. Never breaks ties by recency, ordinal, path order, or lexical order.
"""

from __future__ import annotations

from dataclasses import dataclass

from project_atlas.authority_registry import (
    AuthorityRule,
    registry_version,
    rules_for,
    trust_root,
)
from project_atlas.authority_roles import resolve_artifact_role
from project_atlas.domain import Claim, ConflictRecord, ConflictState
from project_atlas.domain.authority_semantics import (
    ArtifactRole,
    AuthoritativeStateRecord,
    AuthorityDisposition,
    AuthorityEvidence,
)
from project_atlas.domain.temporal import CurrentStateRecord, TemporalStatus


@dataclass(frozen=True, slots=True)
class SourceArtifact:
    """Path+text needed for deterministic role resolution."""

    source_id: str
    path: str
    text: str


def _claim_source_id(claim: Claim) -> str | None:
    for ref in claim.provenance:
        if ref.source_id:
            return ref.source_id
    return None


def _temporally_eligible_ids(disposition: CurrentStateRecord) -> set[str]:
    """Claims that may compete for authority under the domain contract.

    Historical claims remain historical and cannot be resurrected by role.
    For AUTHORITY_PENDING / UNRESOLVED groups, all participating claims that
    are not listed as historical are eligible.
    """
    historical = set(disposition.historical_claim_ids)
    return {cid for cid in disposition.participating_claim_ids if cid not in historical}


def _evidence_for(
    *,
    claim: Claim,
    role: ArtifactRole,
    rule: AuthorityRule,
    artifact: SourceArtifact,
    temporal_status: str,
) -> AuthorityEvidence:
    return AuthorityEvidence(
        rule_id=rule.rule_id,
        trust_root=trust_root(),
        registry_version=registry_version(),
        artifact_role=role,
        claim_id=claim.claim_id,
        source_id=artifact.source_id,
        source_path=artifact.path,
        temporal_status=temporal_status,
        notes=(
            f"role={role.value}; temporal_status={temporal_status}; "
            f"domain={rule.domain.value}"
        ),
    )


def _pending(
    disposition: CurrentStateRecord,
    *,
    rule: AuthorityRule | None,
    rationale: str,
    competing: tuple[str, ...],
    subordinate: tuple[str, ...] = (),
    ineligible: tuple[str, ...] = (),
    evidence: tuple[AuthorityEvidence, ...] = (),
    compilation_id: str,
) -> AuthoritativeStateRecord:
    domain = (
        rule.domain
        if rule is not None
        else rules_for(disposition.subject, disposition.field)[0].domain
        if rules_for(disposition.subject, disposition.field)
        else None
    )
    # Domain is required on the record; only called for matched domains.
    assert domain is not None
    return AuthoritativeStateRecord(
        project_id=disposition.project_id,
        subject=disposition.subject,
        field=disposition.field,
        authority_domain=domain,
        disposition=AuthorityDisposition.AUTHORITY_PENDING,
        rule_id=rule.rule_id if rule else None,
        authoritative_claim_id=None,
        authoritative_value=None,
        authoritative_role=None,
        competing_claim_ids=tuple(sorted(competing)),
        subordinate_claim_ids=tuple(sorted(subordinate)),
        temporally_ineligible_claim_ids=tuple(sorted(ineligible)),
        evidence=tuple(sorted(evidence, key=lambda e: (e.claim_id, e.rule_id))),
        rationale=rationale,
        compilation_id=compilation_id,
        registry_version=registry_version(),
        trust_root=trust_root(),
    )


def _conflict(
    disposition: CurrentStateRecord,
    *,
    rule: AuthorityRule,
    competing: tuple[str, ...],
    evidence: tuple[AuthorityEvidence, ...],
    ineligible: tuple[str, ...],
    compilation_id: str,
) -> AuthoritativeStateRecord:
    return AuthoritativeStateRecord(
        project_id=disposition.project_id,
        subject=disposition.subject,
        field=disposition.field,
        authority_domain=rule.domain,
        disposition=AuthorityDisposition.AUTHORITY_CONFLICT,
        rule_id=rule.rule_id,
        authoritative_claim_id=None,
        authoritative_value=None,
        authoritative_role=None,
        competing_claim_ids=tuple(sorted(competing)),
        subordinate_claim_ids=(),
        temporally_ineligible_claim_ids=tuple(sorted(ineligible)),
        evidence=tuple(sorted(evidence, key=lambda e: (e.claim_id, e.rule_id))),
        rationale=(
            f"{rule.rule_id}: multiple temporally eligible claims satisfy "
            f"authoritative role {rule.authoritative_role.value} with "
            f"conflicting values; fail closed (no recency/ordinal/path tie-break)"
        ),
        compilation_id=compilation_id,
        registry_version=registry_version(),
        trust_root=trust_root(),
    )


def _success(
    disposition: CurrentStateRecord,
    *,
    rule: AuthorityRule,
    winner: Claim,
    role: ArtifactRole,
    subordinate: tuple[str, ...],
    competing: tuple[str, ...],
    ineligible: tuple[str, ...],
    evidence: tuple[AuthorityEvidence, ...],
    compilation_id: str,
) -> AuthoritativeStateRecord:
    return AuthoritativeStateRecord(
        project_id=disposition.project_id,
        subject=disposition.subject,
        field=disposition.field,
        authority_domain=rule.domain,
        disposition=AuthorityDisposition.AUTHORITATIVE,
        rule_id=rule.rule_id,
        authoritative_claim_id=winner.claim_id,
        authoritative_value=winner.value,
        authoritative_role=role,
        competing_claim_ids=tuple(sorted(competing)),
        subordinate_claim_ids=tuple(sorted(subordinate)),
        temporally_ineligible_claim_ids=tuple(sorted(ineligible)),
        evidence=tuple(sorted(evidence, key=lambda e: (e.claim_id, e.rule_id))),
        rationale=(
            f"{rule.rule_id}: selected claim {winner.claim_id} as authoritative "
            f"for domain {rule.domain.value} because artifact role "
            f"{role.value} is the registry-authorized role "
            f"(trust root: {trust_root()}); competing non-authoritative roles "
            f"remain subordinate; temporal eligibility required"
        ),
        compilation_id=compilation_id,
        registry_version=registry_version(),
        trust_root=trust_root(),
    )


def evaluate_disposition(
    disposition: CurrentStateRecord,
    claims_by_id: dict[str, Claim],
    artifacts_by_source: dict[str, SourceArtifact],
    *,
    compilation_id: str,
) -> AuthoritativeStateRecord | None:
    """Evaluate authority for one temporal disposition when a rule applies.

    Returns None when no registry rule matches (no implicit authority).
    """
    matched = rules_for(disposition.subject, disposition.field)
    if not matched:
        return None
    if len(matched) != 1:
        # Multiple rules for one domain is unsupported in MVP — fail closed.
        return _pending(
            disposition,
            rule=None,
            rationale=(
                "malformed authority registry mapping: multiple rules match "
                f"{disposition.subject}/{disposition.field}; fail closed"
            ),
            competing=tuple(disposition.participating_claim_ids),
            compilation_id=compilation_id,
        )

    rule = matched[0]
    eligible_ids = _temporally_eligible_ids(disposition)
    ineligible = tuple(
        sorted(set(disposition.participating_claim_ids) - eligible_ids)
    )
    competing = tuple(sorted(eligible_ids))

    if not eligible_ids:
        return _pending(
            disposition,
            rule=rule,
            rationale=(
                f"{rule.rule_id}: no temporally eligible claims; authority "
                "does not resurrect historical claims"
            ),
            competing=(),
            ineligible=ineligible,
            compilation_id=compilation_id,
        )

    # Temporal CURRENT with a unique current claim: authority still only
    # applies when the rule's role matches; MVP title domain arrives as
    # AUTHORITY_PENDING. For safety, never treat temporal current alone as
    # authoritative without role match.
    evidence: list[AuthorityEvidence] = []
    role_matches: list[tuple[Claim, ArtifactRole, SourceArtifact]] = []
    unknown_roles: list[str] = []
    subordinate: list[str] = []

    for claim_id in sorted(eligible_ids):
        claim = claims_by_id.get(claim_id)
        if claim is None:
            return _pending(
                disposition,
                rule=rule,
                rationale=f"{rule.rule_id}: participating claim missing from claim set",
                competing=competing,
                ineligible=ineligible,
                compilation_id=compilation_id,
            )
        source_id = _claim_source_id(claim)
        if source_id is None or source_id not in artifacts_by_source:
            unknown_roles.append(claim_id)
            continue
        artifact = artifacts_by_source[source_id]
        role = resolve_artifact_role(
            path=artifact.path,
            text=artifact.text,
            subject=disposition.subject,
        )
        temporal_status = (
            TemporalStatus.HISTORICAL.value
            if claim_id in disposition.historical_claim_ids
            else disposition.temporal_status.value
        )
        evidence.append(
            _evidence_for(
                claim=claim,
                role=role,
                rule=rule,
                artifact=artifact,
                temporal_status=temporal_status,
            )
        )
        if role is ArtifactRole.UNKNOWN:
            unknown_roles.append(claim_id)
            continue
        if role is rule.authoritative_role:
            role_matches.append((claim, role, artifact))
        else:
            subordinate.append(claim_id)

    if unknown_roles and not role_matches:
        return _pending(
            disposition,
            rule=rule,
            rationale=(
                f"{rule.rule_id}: source/document role could not be established "
                f"safely for claim(s) {', '.join(sorted(unknown_roles))}; "
                "fail closed (no recency fallback)"
            ),
            competing=competing,
            subordinate=tuple(subordinate),
            ineligible=ineligible,
            evidence=tuple(evidence),
            compilation_id=compilation_id,
        )

    if not role_matches:
        return _pending(
            disposition,
            rule=rule,
            rationale=(
                f"{rule.rule_id}: no temporally eligible claim carries "
                f"authoritative role {rule.authoritative_role.value}; "
                "self-asserted canonical wording does not grant authority"
            ),
            competing=competing,
            subordinate=tuple(subordinate),
            ineligible=ineligible,
            evidence=tuple(evidence),
            compilation_id=compilation_id,
        )

    values = {claim.value for claim, _role, _art in role_matches}
    if len(values) > 1:
        return _conflict(
            disposition,
            rule=rule,
            competing=tuple(c.claim_id for c, _, _ in role_matches),
            evidence=tuple(evidence),
            ineligible=ineligible,
            compilation_id=compilation_id,
        )

    # Unique authoritative value. If multiple claims share the same value and
    # role, pick a deterministic representative by claim_id for identity only —
    # not as precedence among conflicting values (values already agree).
    role_matches.sort(key=lambda item: item[0].claim_id)
    winner, win_role, _ = role_matches[0]
    extra_subordinate = [
        claim.claim_id for claim, _, _ in role_matches[1:]
    ] + subordinate + unknown_roles
    return _success(
        disposition,
        rule=rule,
        winner=winner,
        role=win_role,
        subordinate=tuple(extra_subordinate),
        competing=competing,
        ineligible=ineligible,
        evidence=tuple(evidence),
        compilation_id=compilation_id,
    )


def evaluate_authority(
    claims: list[Claim] | tuple[Claim, ...],
    current_states: tuple[CurrentStateRecord, ...],
    artifacts_by_source: dict[str, SourceArtifact],
    conflicts: list[ConflictRecord],
    *,
    compilation_id: str,
) -> tuple[tuple[AuthoritativeStateRecord, ...], list[ConflictRecord]]:
    """Derive authoritative states and optionally reclassify conflicts."""
    claims_by_id = {claim.claim_id: claim for claim in claims}
    authoritative: list[AuthoritativeStateRecord] = []
    resolved_keys: set[tuple[str, str]] = set()

    for disposition in current_states:
        record = evaluate_disposition(
            disposition,
            claims_by_id,
            artifacts_by_source,
            compilation_id=compilation_id,
        )
        if record is None:
            continue
        authoritative.append(record)
        if (
            record.disposition is AuthorityDisposition.AUTHORITATIVE
            and record.authoritative_claim_id is not None
        ):
            resolved_keys.add((record.subject, record.field))

    out_conflicts: list[ConflictRecord] = []
    for conflict in conflicts:
        key = (conflict.subject, conflict.field)
        if key in resolved_keys and conflict.state is ConflictState.UNRESOLVED:
            auth = next(
                item
                for item in authoritative
                if item.subject == conflict.subject and item.field == conflict.field
            )
            out_conflicts.append(
                conflict.model_copy(
                    update={
                        "state": ConflictState.RESOLVED,
                        "resolution": (
                            "authority-resolution;"
                            f"rule={auth.rule_id};"
                            f"claim={auth.authoritative_claim_id};"
                            "role="
                            + (
                                auth.authoritative_role.value
                                if auth.authoritative_role
                                else "none"
                            )
                            + ";"
                            f"domain={auth.authority_domain.value};"
                            "temporal_basis=preserved"
                        ),
                    }
                )
            )
        else:
            out_conflicts.append(conflict)

    authoritative.sort(key=lambda item: (item.subject, item.field, item.rule_id or ""))
    out_conflicts.sort(key=lambda item: item.conflict_id)
    return tuple(authoritative), out_conflicts
