"""AS-EXPLAIN-001 Band A — structured explainability / provenance receipts.

Consume-only helpers over AS-CORE-007/008 answers and AS-QUERY-DIAG diagnostics.
Receipts are operational provenance metadata — never Layer-B/C truth, never
authority winners, and never subjective trust/confidence scores (EXPL-INV-001).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from project_atlas.domain.knowledge_query import (
    KnowledgeAnswer,
    KnowledgeMultiFieldAnswer,
    QueryDiagnostic,
)

ReceiptKind = Literal["query_point", "query_multifield_item", "query_diagnostic"]

_FORBIDDEN_SCORE_KEYS = frozenset(
    {
        "trust_score",
        "confidence",
        "confidence_score",
        "subjective_trust",
        "trustScore",
        "confidenceScore",
    }
)


class ExplainReceiptError(ValueError):
    """Raised when an explain receipt cannot be built fail-closed."""


def receipt_to_json(receipt: dict[str, Any]) -> str:
    """Serialize a receipt deterministically (NFR-001 / EXPL-FR-007)."""
    _assert_no_trust_scores(receipt)
    return json.dumps(receipt, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def build_explain_receipt_from_answer(
    answer: KnowledgeAnswer,
    *,
    receipt_kind: ReceiptKind = "query_point",
) -> dict[str, Any]:
    """Build a Band A explain receipt from a persisted query answer (EXPL-FR-002/003)."""
    if receipt_kind not in {"query_point", "query_multifield_item"}:
        raise ExplainReceiptError(
            f"receipt_kind {receipt_kind!r} is not valid for KnowledgeAnswer"
        )

    reason_categories: list[str] = []
    provenance_refs: list[dict[str, str]] = []
    evidence_refs: list[dict[str, Any]] = []
    omissions: list[str] = []
    notes: list[str] = [
        "AS-EXPLAIN-001 Band A: consume-only provenance receipt.",
        "No authority/temporal recomputation; no invented claim values.",
    ]

    if answer.authority_disposition is not None:
        reason_categories.append("authority_disposition")
    else:
        omissions.append("authority_layer_absent")

    if answer.temporal_status is not None:
        reason_categories.append("temporal_status")
    else:
        omissions.append("temporal_layer_absent")

    if answer.reason_code is not None:
        reason_categories.append("reason_code")

    if answer.authority_rationale or answer.temporal_rationale:
        reason_categories.append("persisted_rationale")
    if answer.authority_rationale is None:
        omissions.append("authority_rationale_absent")
    if answer.temporal_rationale is None:
        omissions.append("temporal_rationale_absent")

    if answer.claim is None:
        omissions.append("claim_projection_absent")
    else:
        _append_ref(provenance_refs, "claim_id", answer.claim.claim_id)
        if answer.claim.source_id:
            _append_ref(provenance_refs, "source_id", answer.claim.source_id)
        if answer.claim.source_lineage_id:
            _append_ref(
                provenance_refs, "source_lineage_id", answer.claim.source_lineage_id
            )

    if answer.claim_id:
        _append_ref(provenance_refs, "claim_id", answer.claim_id)
    if answer.rule_id:
        _append_ref(provenance_refs, "rule_id", answer.rule_id)
    if answer.trust_root:
        # Objective trust-root identifier from AS-CORE-006 — not a score.
        _append_ref(provenance_refs, "trust_root", answer.trust_root)

    for claim_id in sorted(answer.competing_claim_ids):
        _append_ref(provenance_refs, "claim_id", claim_id)
    for claim_id in sorted(answer.subordinate_claim_ids):
        _append_ref(provenance_refs, "claim_id", claim_id)
    for claim_id in sorted(answer.temporally_ineligible_claim_ids):
        _append_ref(provenance_refs, "claim_id", claim_id)
    if answer.temporal_current_claim_id:
        _append_ref(provenance_refs, "claim_id", answer.temporal_current_claim_id)
        evidence_refs.append(
            {
                "ref_kind": "temporal_current",
                "claim_id": answer.temporal_current_claim_id,
                "source_id": None,
                "rule_id": None,
                "path": None,
            }
        )
    for claim_id in sorted(answer.temporal_historical_claim_ids):
        _append_ref(provenance_refs, "claim_id", claim_id)

    if answer.evidence:
        for item in answer.evidence:
            evidence_refs.append(
                {
                    "ref_kind": "authority_evidence",
                    "claim_id": _optional_str(item.get("claim_id")),
                    "source_id": _optional_str(item.get("source_id")),
                    "rule_id": _optional_str(item.get("rule_id")),
                    "path": None,
                }
            )
    else:
        omissions.append("evidence_absent")

    if answer.compilation_id is None:
        omissions.append("compilation_id_absent")

    if (
        answer.value is None
        and answer.authority_disposition is not None
        and answer.authority_disposition != "authoritative"
    ):
        omissions.append("value_omitted_non_authoritative")

    for path in answer.inspected_artifacts:
        evidence_refs.append(
            {
                "ref_kind": "inspected_artifact",
                "claim_id": None,
                "source_id": None,
                "rule_id": None,
                "path": path,
            }
        )

    # Preserve answer notes as metadata-only; never invent narrative.
    notes.extend(answer.notes)

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "package": "AS-EXPLAIN-001",
        "receipt_kind": receipt_kind,
        "project_id": answer.project_id,
        "subject": answer.subject,
        "field": answer.field,
        "query_kind": answer.kind.value,
        "answer_status": answer.status.value,
        "outcome_class": None,
        "compilation_id": answer.compilation_id,
        "reason_categories": _sorted_unique(reason_categories),
        "provenance_refs": _sorted_refs(provenance_refs),
        "evidence_refs": _sorted_evidence(evidence_refs),
        "omissions": _sorted_unique(omissions),
        "inspected_artifacts": list(answer.inspected_artifacts),
        "notes": list(notes),
    }
    _assert_no_trust_scores(receipt)
    return receipt


def build_explain_receipts_from_multifield(
    envelope: KnowledgeMultiFieldAnswer,
) -> list[dict[str, Any]]:
    """One receipt per multifield item; preserves caller field order (EXPL-FR-003)."""
    return [
        build_explain_receipt_from_answer(item, receipt_kind="query_multifield_item")
        for item in envelope.results
    ]


def build_explain_receipt_from_diagnostic(
    diagnostic: QueryDiagnostic,
) -> dict[str, Any]:
    """Build a receipt referencing DIAG outcome classes only (no answer invention)."""
    reason_categories = ["outcome_class"]
    provenance_refs: list[dict[str, str]] = []
    omissions: list[str] = [
        "authority_rationale_absent",
        "temporal_rationale_absent",
        "claim_projection_absent",
        "evidence_absent",
    ]
    notes = [
        "AS-EXPLAIN-001 Band A: diagnostic-derived receipt.",
        "Integrity/request failures remain owned by AS-QUERY-DIAG-001.",
    ]

    if diagnostic.error_code is not None:
        reason_categories.append("error_code")
        _append_ref(provenance_refs, "error_code", diagnostic.error_code.value)

    if diagnostic.answer_status is None and diagnostic.outcome_class.value in {
        "integrity_failure",
        "request_invalid",
    }:
        omissions.append("authority_layer_absent")
        omissions.append("temporal_layer_absent")
        reason_categories.append("missing_evidence")

    if diagnostic.compilation_id is None:
        omissions.append("compilation_id_absent")

    evidence_refs = [
        {
            "ref_kind": "inspected_artifact",
            "claim_id": None,
            "source_id": None,
            "rule_id": None,
            "path": path,
        }
        for path in diagnostic.inspected_artifacts
    ]

    if diagnostic.message:
        # Metadata-only; never echo secret-shaped payloads beyond DIAG's own message.
        notes.append(f"diagnostic_message_present={bool(diagnostic.message)}")

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "package": "AS-EXPLAIN-001",
        "receipt_kind": "query_diagnostic",
        "project_id": diagnostic.project_id,
        "subject": diagnostic.subject,
        "field": diagnostic.field,
        "query_kind": diagnostic.kind.value if diagnostic.kind is not None else None,
        "answer_status": (
            diagnostic.answer_status.value if diagnostic.answer_status is not None else None
        ),
        "outcome_class": diagnostic.outcome_class.value,
        "compilation_id": diagnostic.compilation_id,
        "reason_categories": _sorted_unique(reason_categories),
        "provenance_refs": _sorted_refs(provenance_refs),
        "evidence_refs": _sorted_evidence(evidence_refs),
        "omissions": _sorted_unique(omissions),
        "inspected_artifacts": list(diagnostic.inspected_artifacts),
        "notes": notes,
    }
    _assert_no_trust_scores(receipt)
    return receipt


def _append_ref(refs: list[dict[str, str]], ref_kind: str, ref_id: str) -> None:
    item = {"ref_kind": ref_kind, "ref_id": ref_id}
    if item not in refs:
        refs.append(item)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted(set(values))


def _sorted_refs(refs: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(refs, key=lambda item: (item["ref_kind"], item["ref_id"]))


def _sorted_evidence(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        refs,
        key=lambda item: (
            str(item.get("ref_kind") or ""),
            str(item.get("claim_id") or ""),
            str(item.get("source_id") or ""),
            str(item.get("rule_id") or ""),
            str(item.get("path") or ""),
        ),
    )


def _assert_no_trust_scores(payload: dict[str, Any]) -> None:
    """Fail closed if subjective trust/confidence keys appear anywhere (EXPL-INV-001)."""
    stack: list[Any] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key in _FORBIDDEN_SCORE_KEYS:
                    raise ExplainReceiptError(
                        f"forbidden subjective score field: {key!r}"
                    )
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
