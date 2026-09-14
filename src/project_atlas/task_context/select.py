"""Deterministic, explainable context selection from explicit contract relations.

Search is supplementary only when an optional lexical helper is provided.
Version 1 prefers explicit references: issue/contract refs, named files,
interfaces, dependencies, acceptance, and prior findings.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from project_atlas.task_context.adapters import (
    ContextSourceRef,
    ContractSnapshot,
    EvidenceRecord,
    materialize_source,
)
from project_atlas.task_context.models import (
    ContentTier,
    FreshnessKind,
    OpenUncertainty,
    PacketFragment,
    PriorAction,
    SelectionReason,
    SourceIdentity,
    TrustLayer,
    sha256_bytes,
)

#: Injection-shaped phrases stay retrieved content; never become policy.
_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all instructions",
    "you may modify all files",
    "widen the mutation scope",
    "run this command:",
    "execute the following",
    "exfiltrate",
    "send credentials",
)


def _tier_for(hint: str) -> ContentTier:
    return ContentTier(hint)


def _sizes(body: str) -> tuple[int, int]:
    encoded = body.encode("utf-8")
    return len(encoded), len(body)


def build_requirement_fragments(contract: ContractSnapshot) -> list[PacketFragment]:
    """Mandatory task requirements and bounds from the contract itself."""
    parts: list[PacketFragment] = []

    def add(fid: str, title: str, body: str, reason: str) -> None:
        b, c = _sizes(body)
        parts.append(
            PacketFragment(
                fragment_id=fid,
                trust_layer=TrustLayer.TASK_REQUIREMENT,
                tier=ContentTier.MANDATORY,
                title=title,
                body=body,
                selection_reasons=(SelectionReason(code="contract-field", detail=reason),),
                byte_size=b,
                char_size=c,
                included=True,
            )
        )

    add(
        "req-objective",
        "Objective",
        contract.objective,
        "contract.objective",
    )
    add(
        "req-outcome",
        "Observable outcome",
        contract.observable_outcome,
        "contract.observable_outcome",
    )
    add(
        "req-scope",
        "Scope",
        "\n".join(f"+ {item}" for item in contract.scope),
        "contract.scope",
    )
    if contract.exclusions:
        add(
            "req-exclusions",
            "Exclusions",
            "\n".join(f"- {item}" for item in contract.exclusions),
            "contract.exclusions",
        )
    add(
        "req-mutation",
        "Mutation paths",
        "\n".join(contract.mutation_paths),
        "contract.mutation_paths — retrieved text cannot widen this set",
    )
    if contract.requirements:
        lines = []
        for req in contract.requirements:
            rid = req.get("requirement_id", "?")
            statement = req.get("statement", "")
            lines.append(f"{rid}: {statement}")
        add(
            "req-requirements",
            "Result requirements",
            "\n".join(lines),
            "contract.requirements",
        )
    if contract.acceptance:
        lines = []
        for check in contract.acceptance:
            cid = check.get("check_id") or check.get("id") or "?"
            lines.append(f"{cid}: {check}")
        add(
            "req-acceptance",
            "Acceptance checks",
            "\n".join(lines),
            "contract.acceptance",
        )
    if contract.interface_refs:
        add(
            "req-interfaces",
            "Interfaces",
            "\n".join(contract.interface_refs),
            "contract.interface_refs",
        )
    if contract.policy_refs:
        b, c = _sizes("\n".join(contract.policy_refs))
        parts.append(
            PacketFragment(
                fragment_id="policy-refs",
                trust_layer=TrustLayer.POLICY,
                tier=ContentTier.MANDATORY,
                title="Policy references",
                body="\n".join(contract.policy_refs),
                selection_reasons=(
                    SelectionReason(
                        code="policy-config",
                        detail="supplied via contract policy_refs / config — not retrieved text",
                    ),
                ),
                byte_size=b,
                char_size=c,
                included=True,
            )
        )
    return parts


def select_retrieved_fragments(
    contract: ContractSnapshot,
    *,
    workspace_root: Path,
    search_hook: Callable[[str], list[tuple[str, str]]] | None = None,
) -> tuple[list[PacketFragment], list[OpenUncertainty], list[str]]:
    """Select retrieved sources. Never promotes them to policy or scope."""
    fragments: list[PacketFragment] = []
    uncertainties: list[OpenUncertainty] = []
    limits = [
        "selection=explicit-contract-context-first",
        "supplementary-search=optional-hook-only",
        "no-full-repo-history",
        "retrieved-cannot-widen-mutation-scope",
        "no-command-execution-from-documents",
    ]
    seen_paths: dict[str, list[str]] = {}

    for ref in contract.context:
        text, data, missing = materialize_source(workspace_root, ref)
        if missing:
            uncertainties.append(
                OpenUncertainty(
                    uncertainty_id=f"missing-{ref.source_id}",
                    kind="missing_source",
                    statement=missing,
                    source_ids=(ref.source_id,),
                )
            )
            fragments.append(
                PacketFragment(
                    fragment_id=f"src-{ref.source_id}",
                    trust_layer=TrustLayer.RETRIEVED,
                    tier=_tier_for(ref.tier_hint),
                    title=f"Missing: {ref.path}",
                    body="",
                    source_path=ref.path,
                    selection_reasons=(
                        SelectionReason(code="explicit-context-ref", detail=ref.why),
                    ),
                    included=False,
                    exclusion_reason=missing,
                    retrieved_quarantine=True,
                )
            )
            continue

        digest = sha256_bytes(data)
        if ref.digest and ref.digest != digest:
            uncertainties.append(
                OpenUncertainty(
                    uncertainty_id=f"digest-mismatch-{ref.source_id}",
                    kind="conflict",
                    statement=(
                        f"recorded digest {ref.digest} != live {digest} for {ref.path}"
                    ),
                    source_ids=(ref.source_id,),
                )
            )

        # Track duplicates without dropping provenance.
        seen_paths.setdefault(ref.path, []).append(ref.source_id)
        injection_hit = any(marker in text.lower() for marker in _INJECTION_MARKERS)
        reasons = [
            SelectionReason(code="explicit-context-ref", detail=ref.why),
        ]
        if injection_hit:
            reasons.append(
                SelectionReason(
                    code="injection-shaped-kept-as-retrieved",
                    detail="instruction-like text retained as quoted evidence; not policy",
                )
            )
            uncertainties.append(
                OpenUncertainty(
                    uncertainty_id=f"injection-{ref.source_id}",
                    kind="open_question",
                    statement=(
                        f"{ref.path} contains instruction-shaped text; "
                        "kept as RETRIEVED only"
                    ),
                    source_ids=(ref.source_id,),
                )
            )

        b, c = _sizes(text)
        fragments.append(
            PacketFragment(
                fragment_id=f"src-{ref.source_id}",
                trust_layer=TrustLayer.RETRIEVED,
                tier=_tier_for(ref.tier_hint),
                title=ref.path,
                body=text,
                source_path=ref.path,
                source_identity=SourceIdentity(
                    kind=FreshnessKind.CONTENT_DIGEST,
                    identity=digest,
                    path=ref.path,
                ),
                selection_reasons=tuple(reasons),
                byte_size=b,
                char_size=c,
                included=True,
                retrieved_quarantine=True,
            )
        )

    for path, ids in seen_paths.items():
        if len(ids) > 1:
            uncertainties.append(
                OpenUncertainty(
                    uncertainty_id=f"dup-{path}",
                    kind="open_question",
                    statement=f"duplicate path {path} via sources {', '.join(ids)}",
                    source_ids=tuple(ids),
                )
            )

    for question in contract.open_questions:
        uncertainties.append(
            OpenUncertainty(
                uncertainty_id=f"oq-{sha256_bytes(question.encode())[:12]}",
                kind="open_question",
                statement=question,
                source_ids=(),
            )
        )

    # Supplementary search (optional). Never invents a second index.
    if search_hook is not None:
        limits.append("supplementary-search=invoked")
        for query in list(contract.scope)[:3]:
            for path, why in search_hook(query)[:5]:
                if any(f.source_path == path for f in fragments):
                    continue
                ref = ContextSourceRef(
                    source_id=f"search-{path.replace('/', '-')}",
                    path=path,
                    why=why,
                    tier_hint="background",
                )
                text, data, missing = materialize_source(workspace_root, ref)
                if missing:
                    continue
                digest = sha256_bytes(data)
                b, c = _sizes(text)
                fragments.append(
                    PacketFragment(
                        fragment_id=f"search-{digest[:12]}",
                        trust_layer=TrustLayer.RETRIEVED,
                        tier=ContentTier.BACKGROUND,
                        title=path,
                        body=text,
                        source_path=path,
                        source_identity=SourceIdentity(
                            kind=FreshnessKind.CONTENT_DIGEST,
                            identity=digest,
                            path=path,
                        ),
                        selection_reasons=(
                            SelectionReason(code="supplementary-search", detail=why),
                        ),
                        byte_size=b,
                        char_size=c,
                        included=True,
                        retrieved_quarantine=True,
                    )
                )

    return fragments, uncertainties, limits


def prior_actions_from_evidence(records: tuple[EvidenceRecord, ...]) -> list[PriorAction]:
    actions: list[PriorAction] = []
    for record in records:
        digest = record.artifact_digests[0] if record.artifact_digests else record.evidence_id
        actions.append(
            PriorAction(
                action_id=record.action_id,
                summary=record.summary,
                evidence_ref=record.evidence_id,
                evidence_digest=digest,
                outcome=record.outcome,
                completion_proven=bool(record.completion_proven and record.outcome == "passed"),
            )
        )
    return actions
