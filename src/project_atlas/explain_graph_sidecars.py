"""AS-EXPLAIN-001 Band B — graph explain sidecars.

Consume-only enrichment over public AS-GRAPH-002/003 contracts.
Sidecars are derived operational metadata — never query winners, never
authority, and never subjective trust/confidence scores (EXPL-INV-001).

Missing or hash-mismatched graph artifacts yield structured absent/refuse
dispositions and must not be treated as query failures (EXPL-FR-B01/B03).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Literal

from project_atlas.graph_relationships import RelationshipRecord
from project_atlas.graph_resolution import IdentityExplanation, ResolvedNode

SidecarKind = Literal[
    "resolved_node",
    "identity_explanation",
    "relationship",
    "graph_absent",
    "hash_refused",
]
Disposition = Literal["present", "absent", "refused_hash_mismatch"]

TRUTH_BOUNDARY = "GRAPH RELATIONSHIP ≠ AUTOMATIC AUTHORITY"

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


class ExplainGraphSidecarError(ValueError):
    """Raised when a graph explain sidecar cannot be built fail-closed."""


def sidecar_to_json(sidecar: dict[str, Any]) -> str:
    """Serialize a sidecar deterministically (NFR-001 / EXPL-FR-007)."""
    _assert_no_trust_scores(sidecar)
    return json.dumps(sidecar, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def build_graph_absent_sidecar(
    *,
    project_id: str | None = None,
    note: str = "graph_artifacts_absent",
) -> dict[str, Any]:
    """Structured absent sidecar when graph inputs are missing (EXPL-FR-B01)."""
    sidecar = _base_sidecar(
        sidecar_kind="graph_absent",
        disposition="absent",
        project_id=project_id,
        reason_categories=["graph_absent", "derived_only"],
        omissions=["graph_artifacts_absent"],
        notes=[
            "AS-EXPLAIN-001 Band B: graph sidecar absent.",
            "Missing graph ≠ query failure.",
            note,
        ],
    )
    _assert_no_trust_scores(sidecar)
    return sidecar


def build_sidecar_from_resolved_node(
    node: ResolvedNode | Mapping[str, Any],
    *,
    expected_artifact_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a sidecar from a GRAPH-002 resolved-node / quarantine candidate."""
    payload = node.as_dict() if isinstance(node, ResolvedNode) else dict(node)
    project_id = _optional_str(payload.get("project_id"))
    artifact_refs, hash_ok = _normalize_artifact_refs(
        payload.get("source_artifact_refs"),
        expected_artifact_hashes=expected_artifact_hashes,
    )
    if not hash_ok:
        return _hash_refused_sidecar(
            project_id=project_id,
            artifact_refs=artifact_refs,
            intended_kind="resolved_node",
        )

    reason_categories = ["resolved_node", "derived_only"]
    omissions: list[str] = []
    graph_refs: list[dict[str, str]] = []
    notes = [
        "AS-EXPLAIN-001 Band B: consume-only resolved-node sidecar.",
        "GRAPH RELATIONSHIP ≠ AUTOMATIC AUTHORITY — not a query winner.",
    ]

    graphify_node_id = _optional_str(payload.get("graphify_node_id"))
    if graphify_node_id:
        _append_ref(graph_refs, "graphify_node_id", graphify_node_id)

    resolved_entity_id = _optional_str(payload.get("resolved_entity_id"))
    if resolved_entity_id:
        _append_ref(graph_refs, "resolved_entity_id", resolved_entity_id)
    else:
        omissions.append("resolved_entity_absent")

    status = _optional_str(payload.get("status"))
    if status == "quarantine_candidate":
        reason_categories.append("quarantine_candidate")

    if expected_artifact_hashes is None and artifact_refs:
        omissions.append("artifact_hash_unchecked")

    sidecar = _base_sidecar(
        sidecar_kind="resolved_node",
        disposition="present",
        project_id=project_id,
        reason_categories=reason_categories,
        graph_refs=graph_refs,
        artifact_refs=artifact_refs,
        omissions=omissions,
        notes=notes,
        graphify_node_id=graphify_node_id,
        resolved_entity_id=resolved_entity_id,
        resolution_step=_optional_str(payload.get("resolution_step")),
        resolve_status=status,
    )
    _assert_no_trust_scores(sidecar)
    return sidecar


def build_sidecar_from_identity_explanation(
    explanation: IdentityExplanation | Mapping[str, Any],
    *,
    expected_artifact_hashes: Mapping[str, str] | None = None,
    artifact_refs: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a sidecar from a GRAPH-002 identity explanation (categorical labels only)."""
    payload = (
        explanation.as_dict()
        if isinstance(explanation, IdentityExplanation)
        else dict(explanation)
    )
    project_id = _optional_str(payload.get("project_id"))
    normalized_refs, hash_ok = _normalize_artifact_refs(
        artifact_refs,
        expected_artifact_hashes=expected_artifact_hashes,
    )
    if not hash_ok:
        return _hash_refused_sidecar(
            project_id=project_id,
            artifact_refs=normalized_refs,
            intended_kind="identity_explanation",
        )

    graph_refs: list[dict[str, str]] = []
    omissions: list[str] = []
    graphify_node_id = _optional_str(payload.get("graphify_node_id"))
    if graphify_node_id:
        _append_ref(graph_refs, "graphify_node_id", graphify_node_id)

    # GRAPH-002 categorical label — never a subjective score field named "confidence".
    identity_label = _optional_str(payload.get("confidence"))
    if identity_label is None:
        omissions.append("identity_explanation_absent")

    if expected_artifact_hashes is None and normalized_refs:
        omissions.append("artifact_hash_unchecked")
    if not normalized_refs:
        omissions.append("artifact_hash_unchecked")

    notes = [
        "AS-EXPLAIN-001 Band B: identity-explanation sidecar.",
        "identity_confidence_label is categorical GRAPH-002 vocabulary, not a score.",
    ]
    explanation_notes = _optional_str(payload.get("notes"))
    if explanation_notes:
        notes.append(f"identity_notes_present={bool(explanation_notes)}")

    sidecar = _base_sidecar(
        sidecar_kind="identity_explanation",
        disposition="present",
        project_id=project_id,
        reason_categories=["identity_explanation", "derived_only"],
        graph_refs=graph_refs,
        artifact_refs=normalized_refs,
        omissions=omissions,
        notes=notes,
        graphify_node_id=graphify_node_id,
        resolution_step=_optional_str(payload.get("winning_step")),
        identity_confidence_label=identity_label,
    )
    _assert_no_trust_scores(sidecar)
    return sidecar


def build_sidecar_from_relationship(
    record: RelationshipRecord | Mapping[str, Any],
    *,
    expected_artifact_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a sidecar from a GRAPH-003 relationship record (EXPL-FR-B02/B03)."""
    payload = record.as_dict() if isinstance(record, RelationshipRecord) else dict(record)
    project_id = _optional_str(payload.get("project_id"))
    provenance = payload.get("provenance")
    raw_refs: list[Any] = []
    if isinstance(provenance, Mapping):
        refs = provenance.get("graphify_artifact_refs")
        if isinstance(refs, list):
            raw_refs = list(refs)
    artifact_refs, hash_ok = _normalize_artifact_refs(
        raw_refs,
        expected_artifact_hashes=expected_artifact_hashes,
    )
    if not hash_ok:
        return _hash_refused_sidecar(
            project_id=project_id,
            artifact_refs=artifact_refs,
            intended_kind="relationship",
        )

    graph_refs: list[dict[str, str]] = []
    omissions: list[str] = []
    relationship_id = _optional_str(payload.get("relationship_id"))
    if relationship_id:
        _append_ref(graph_refs, "relationship_id", relationship_id)
    else:
        omissions.append("relationship_absent")

    fingerprint = _optional_str(payload.get("relationship_fingerprint"))
    if fingerprint:
        _append_ref(graph_refs, "relationship_fingerprint", fingerprint)

    source_entity_id = _optional_str(payload.get("source_entity_id"))
    target_entity_id = _optional_str(payload.get("target_entity_id"))
    if source_entity_id:
        _append_ref(graph_refs, "source_entity_id", source_entity_id)
    if target_entity_id:
        _append_ref(graph_refs, "target_entity_id", target_entity_id)

    if isinstance(provenance, Mapping):
        edge_ids = provenance.get("graphify_edge_ids")
        if isinstance(edge_ids, list):
            for edge_id in sorted(str(item) for item in edge_ids if item):
                _append_ref(graph_refs, "graphify_edge_id", edge_id)

    if expected_artifact_hashes is None and artifact_refs:
        omissions.append("artifact_hash_unchecked")

    notes = [
        "AS-EXPLAIN-001 Band B: relationship sidecar over GRAPH-003 public contract.",
        "Never elevate relationship to query/authority winner.",
    ]

    sidecar = _base_sidecar(
        sidecar_kind="relationship",
        disposition="present",
        project_id=project_id,
        reason_categories=["relationship_record", "derived_only"],
        graph_refs=graph_refs,
        artifact_refs=artifact_refs,
        omissions=omissions,
        notes=notes,
        relationship_id=relationship_id,
        relationship_type=_optional_str(payload.get("relationship_type")),
        link_quality=_optional_str(payload.get("link_quality")),
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
    )
    _assert_no_trust_scores(sidecar)
    return sidecar


def _hash_refused_sidecar(
    *,
    project_id: str | None,
    artifact_refs: list[dict[str, str]],
    intended_kind: str,
) -> dict[str, Any]:
    sidecar = _base_sidecar(
        sidecar_kind="hash_refused",
        disposition="refused_hash_mismatch",
        project_id=project_id,
        reason_categories=["hash_mismatch", "derived_only"],
        artifact_refs=artifact_refs,
        omissions=["payload_omitted_hash_mismatch"],
        notes=[
            "AS-EXPLAIN-001 Band B: refused sidecar due to artifact hash mismatch.",
            f"intended_kind={intended_kind}",
            "Hash mismatch ≠ query failure; graph enrichment withheld (EXPL-FR-B03).",
        ],
    )
    _assert_no_trust_scores(sidecar)
    return sidecar


def _base_sidecar(
    *,
    sidecar_kind: SidecarKind,
    disposition: Disposition,
    project_id: str | None,
    reason_categories: list[str],
    notes: list[str],
    graph_refs: list[dict[str, str]] | None = None,
    artifact_refs: list[dict[str, str]] | None = None,
    omissions: list[str] | None = None,
    graphify_node_id: str | None = None,
    resolved_entity_id: str | None = None,
    resolution_step: str | None = None,
    resolve_status: str | None = None,
    identity_confidence_label: str | None = None,
    relationship_id: str | None = None,
    relationship_type: str | None = None,
    link_quality: str | None = None,
    source_entity_id: str | None = None,
    target_entity_id: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "package": "AS-EXPLAIN-001",
        "sidecar_kind": sidecar_kind,
        "disposition": disposition,
        "project_id": project_id,
        "graphify_node_id": graphify_node_id,
        "resolved_entity_id": resolved_entity_id,
        "resolution_step": resolution_step,
        "resolve_status": resolve_status,
        "identity_confidence_label": identity_confidence_label,
        "relationship_id": relationship_id,
        "relationship_type": relationship_type,
        "link_quality": link_quality,
        "source_entity_id": source_entity_id,
        "target_entity_id": target_entity_id,
        "reason_categories": _sorted_unique(reason_categories),
        "graph_refs": _sorted_refs(graph_refs or []),
        "artifact_refs": _sorted_artifacts(artifact_refs or []),
        "omissions": _sorted_unique(omissions or []),
        "notes": list(notes),
        "truth_boundary": TRUTH_BOUNDARY,
    }


def _normalize_artifact_refs(
    refs: Any,
    *,
    expected_artifact_hashes: Mapping[str, str] | None,
) -> tuple[list[dict[str, str]], bool]:
    if refs is None:
        return [], True
    if not isinstance(refs, list):
        raise ExplainGraphSidecarError("artifact_refs must be a list")

    normalized: list[dict[str, str]] = []
    hash_ok = True
    for item in refs:
        if not isinstance(item, Mapping):
            raise ExplainGraphSidecarError("artifact_ref must be an object")
        relative_path = _optional_str(item.get("relative_path"))
        sha256 = _optional_str(item.get("sha256"))
        if relative_path is None or sha256 is None:
            raise ExplainGraphSidecarError("artifact_ref requires relative_path and sha256")
        if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
            raise ExplainGraphSidecarError("artifact_ref sha256 must be 64 lowercase hex")

        if expected_artifact_hashes is None:
            status = "unchecked"
        elif relative_path not in expected_artifact_hashes:
            status = "missing_expected"
            hash_ok = False
        elif expected_artifact_hashes[relative_path] == sha256:
            status = "matched"
        else:
            status = "mismatched"
            hash_ok = False

        normalized.append(
            {
                "relative_path": relative_path,
                "sha256": sha256,
                "hash_status": status,
            }
        )
    return normalized, hash_ok


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


def _sorted_artifacts(refs: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        refs,
        key=lambda item: (item["relative_path"], item["sha256"], item["hash_status"]),
    )


def _assert_no_trust_scores(payload: dict[str, Any]) -> None:
    """Fail closed if subjective trust/confidence keys appear anywhere (EXPL-INV-001)."""
    stack: list[Any] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key in _FORBIDDEN_SCORE_KEYS:
                    raise ExplainGraphSidecarError(
                        f"forbidden subjective score field: {key!r}"
                    )
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
