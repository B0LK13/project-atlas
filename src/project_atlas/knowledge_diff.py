"""AS-2.2-KDIFF-001 — Knowledge Diff / Time Machine P0 (read-only).

A bounded, deterministic, offline read lens over already-persisted Atlas state:

* **as-of read** — for a project, which claim was valid at a declared
  reference *valid-time* (per subject+field), with the Core-derived authority
  disposition, freshness signal, and unresolved-conflict membership attached.
* **T1→T2 diff** — per subject+field, what changed between two reference points:
  added / removed / value-changed / authority-changed / freshness-changed /
  conflict-changed, plus honest ``unresolved_delta`` when either side is
  temporally unknown.

Design honours the AS-2.2-TIME-MACHINE prep contracts (as-of ≠ authority,
diff ≠ mutation, no silent overlap winner, wall-clock ≠ valid-time, graph ≠
authority, LLM ≠ authority) while binding real persisted state rather than
fixtures. It **reuses** — never re-derives — Core truth:

* temporal selection → :func:`project_atlas.bitemporal.evaluate_as_of`
  (AS-2.0-TEMPORAL-001; fail-closed overlap / malformed / wall-clock handling);
* authority disposition → persisted ``state/authoritative-state`` (AS-CORE-006);
* freshness → portfolio ``generated/portfolio/stale-knowledge.json`` objective
  labels; conflicts → unresolved ``review/conflicts`` entries.

Invariants: project scope is REQUIRED (fail-closed); UNKNOWN stays UNKNOWN
(missing temporal data never invents a current); graph ≠ authority; model ≠
authority; NO canonical writes (read-only); deterministic output (no wall-clock,
``sort_keys=True``); bounded subject fanout.

Truth boundaries:
  KDIFF AS-OF ≠ AUTHORITY / ≠ WALL-CLOCK NOW / ≠ LAYER B MUTATION
  KDIFF T1→T2 ≠ AUTHORITY / ≠ WALL-CLOCK NOW / ≠ LAYER B MUTATION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from project_atlas.bitemporal import (
    BitemporalError,
    ClaimValidityWindow,
    evaluate_as_of,
)
from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.runtime_22 import (
    # Reuse the established objective-signal readers (do not duplicate truth logic).
    _load_portfolio_freshness,
    _load_unresolved_claim_conflicts,
)
from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.secrets import scan_text

PACKAGE_ID = "AS-2.2-KDIFF-001"
AS_OF_KIND = "kdiff-as-of-snapshot"
DIFF_KIND = "kdiff-record"
TRUTH_AS_OF = "KDIFF AS-OF ≠ AUTHORITY / ≠ WALL-CLOCK NOW / ≠ LAYER B MUTATION"
TRUTH_DIFF = "KDIFF T1→T2 ≠ AUTHORITY / ≠ WALL-CLOCK NOW / ≠ LAYER B MUTATION"

DEFAULT_SUBJECT_CAP = 500
MAX_SUBJECT_CAP = 5000

_VALUE_SKETCH_MAX = 200
_REDACTED_SKETCH = "[redacted: secret-shaped value]"

# Temporal dispositions treated as "definite" (comparable) vs "uncertain".
_DEFINITE = frozenset({"selected", "not_found"})
_FRESHNESS_RANK = {"fresh": 0, "unknown": 1, "stale": 2}

AuthorityRole = Literal[
    "authoritative",
    "competing",
    "subordinate",
    "authority-pending",
    "known-nonwinner",
    "unknown",
]


class KnowledgeDiffError(ValueError):
    """Fail-closed AS-2.2-KDIFF-001 error (CLI exit 1)."""


@dataclass(frozen=True, slots=True)
class _Cell:
    """Internal per subject+field projection at one reference valid-time."""

    subject: str
    field: str
    disposition: str  # selected | not_found | unresolved | unknown
    selected_claim_id: str | None
    value: str | None
    authority_disposition: str | None
    authority_role: str
    freshness: str
    conflict_state: str
    reason: str
    conflict_ids: tuple[str, ...] = ()
    candidate_claim_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _ClaimInfo:
    subject: str
    field: str
    value: str
    source_ids: tuple[str, ...]


@dataclass
class _ProjectState:
    project_id: str
    vault: Path
    claims: dict[str, _ClaimInfo] = field(default_factory=dict)
    windows_by_key: dict[tuple[str, str], list[ClaimValidityWindow]] = field(
        default_factory=dict
    )
    authority_by_key: dict[tuple[str, str], dict[str, Any]] = field(
        default_factory=dict
    )
    keys: tuple[tuple[str, str], ...] = ()
    freshness_by_source: dict[str, str] = field(default_factory=dict)
    conflicts_by_claim: dict[str, list[str]] = field(default_factory=dict)
    inspected: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Read-only state loading
# ---------------------------------------------------------------------------


def _resolve_vault(vault: Path) -> Path:
    try:
        root = vault.expanduser().resolve()
    except OSError as exc:
        raise KnowledgeDiffError(f"kdiff-vault-unresolved:{exc}") from exc
    if not root.is_dir():
        raise KnowledgeDiffError(f"kdiff-vault-not-a-directory:{root}")
    return root


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KnowledgeDiffError(f"kdiff-state-missing:{path.name}") from exc
    except (OSError, UnicodeError) as exc:
        raise KnowledgeDiffError(f"kdiff-state-unreadable:{path.name}:{exc}") from exc
    except json.JSONDecodeError as exc:
        raise KnowledgeDiffError(f"kdiff-state-corrupt:{path.name}:{exc}") from exc
    if not isinstance(raw, dict):
        raise KnowledgeDiffError(f"kdiff-state-not-object:{path.name}")
    return raw


def _validate_project_id(project_id: str) -> str:
    token = project_id.strip() if isinstance(project_id, str) else ""
    if not token:
        # Fail-closed: project scope is REQUIRED (like the AS-2.0 read surfaces).
        raise KnowledgeDiffError("kdiff-project-scope-required")
    return token


def _load_claims(
    root: Path, project_id: str, inspected: list[str]
) -> dict[str, _ClaimInfo]:
    rel = f"state/claims/{project_id}.json"
    path = root / "state" / "claims" / f"{project_id}.json"
    if not path.is_file():
        raise KnowledgeDiffError(f"kdiff-claims-missing:{rel}")
    inspected.append(rel)
    raw = _load_json_object(path)
    claims: dict[str, _ClaimInfo] = {}
    entries = raw.get("claims")
    if not isinstance(entries, list):
        raise KnowledgeDiffError(f"kdiff-claims-malformed:{rel}")
    for item in entries:
        if not isinstance(item, dict):
            raise KnowledgeDiffError(f"kdiff-claim-entry-malformed:{rel}")
        claim_id = str(item.get("claim_id") or "").strip()
        subject = str(item.get("subject") or "").strip()
        field_name = str(item.get("field") or "").strip()
        value = str(item.get("value") or "")
        if not claim_id or not subject or not field_name:
            raise KnowledgeDiffError(f"kdiff-claim-entry-incomplete:{rel}")
        source_ids: set[str] = set()
        prov = item.get("provenance")
        if isinstance(prov, list):
            for ref in prov:
                if isinstance(ref, dict):
                    sid = ref.get("source_id")
                    if isinstance(sid, str) and sid:
                        source_ids.add(sid)
        claims[claim_id] = _ClaimInfo(
            subject=subject,
            field=field_name,
            value=value,
            source_ids=tuple(sorted(source_ids)),
        )
    return claims


def _load_windows(
    root: Path,
    claims: dict[str, _ClaimInfo],
    *,
    knowledge_compilation_id: str | None,
    inspected: list[str],
) -> dict[tuple[str, str], list[ClaimValidityWindow]]:
    """Group AS-2.0-TEMPORAL-001 validity windows by (subject, field).

    Only windows whose claim belongs to this project (present in ``claims``)
    are considered — cross-project windows never leak. Optional
    ``knowledge_compilation_id`` binds the knowledge-time boundary.
    """
    by_key: dict[tuple[str, str], list[ClaimValidityWindow]] = {}
    catalog_dir = root / "generated" / "ops" / "bitemporal"
    if not catalog_dir.is_dir():
        return by_key
    for path in sorted(catalog_dir.glob("*.json")):
        raw = _load_json_object(path)
        windows = raw.get("windows")
        if not isinstance(windows, list):
            continue
        inspected.append(path.relative_to(root).as_posix())
        for entry in windows:
            if not isinstance(entry, dict):
                continue
            claim_id = str(entry.get("claim_id") or "").strip()
            info = claims.get(claim_id)
            if info is None:
                continue  # not part of this project scope
            window_cid = str(entry.get("knowledge_compilation_id") or "").strip()
            if knowledge_compilation_id is not None and (
                window_cid != knowledge_compilation_id
            ):
                continue
            valid_from = str(entry.get("valid_from") or "").strip()
            valid_to_raw = entry.get("valid_to")
            valid_to = (
                str(valid_to_raw).strip()
                if isinstance(valid_to_raw, str) and valid_to_raw.strip()
                else None
            )
            evidence_kind = str(entry.get("evidence_kind") or "unknown").strip()
            window = ClaimValidityWindow(
                claim_id=claim_id,
                valid_from=valid_from,
                knowledge_compilation_id=window_cid or "unknown-compilation",
                valid_to=valid_to,
                evidence_kind=_coerce_evidence_kind(evidence_kind),
            )
            by_key.setdefault((info.subject, info.field), []).append(window)
    for key in by_key:
        by_key[key].sort(key=lambda w: (w.claim_id, w.valid_from))
    return by_key


def _coerce_evidence_kind(raw: str) -> Any:
    allowed = {
        "semantic-event",
        "document-declared",
        "source-version",
        "unknown",
    }
    return raw if raw in allowed else "unknown"


def _load_authority(
    root: Path, project_id: str, inspected: list[str]
) -> dict[tuple[str, str], dict[str, Any]]:
    rel = f"state/authoritative-state/{project_id}.json"
    path = root / "state" / "authoritative-state" / f"{project_id}.json"
    if not path.is_file():
        return {}
    inspected.append(rel)
    raw = _load_json_object(path)
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    entries = raw.get("authoritative_states")
    if not isinstance(entries, list):
        return by_key
    for item in entries:
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject") or "").strip()
        field_name = str(item.get("field") or "").strip()
        if not subject or not field_name:
            continue
        by_key[(subject, field_name)] = item
    return by_key


def _load_state(
    vault: Path,
    project_id: str,
    *,
    knowledge_compilation_id: str | None,
    subject_cap: int,
) -> _ProjectState:
    root = _resolve_vault(vault)
    inspected: list[str] = []
    claims = _load_claims(root, project_id, inspected)
    windows_by_key = _load_windows(
        root,
        claims,
        knowledge_compilation_id=knowledge_compilation_id,
        inspected=inspected,
    )
    authority_by_key = _load_authority(root, project_id, inspected)

    freshness = _load_portfolio_freshness(root)
    if freshness:
        inspected.append("generated/portfolio/stale-knowledge.json")
    conflicts, _records = _load_unresolved_claim_conflicts(root)
    if (root / "review" / "conflicts").is_dir():
        inspected.append("review/conflicts")

    # Universe of subject+field keys = temporal windows union authority projections.
    universe: set[tuple[str, str]] = set(windows_by_key)
    universe.update(authority_by_key)
    ordered_keys = sorted(universe)
    capped_keys = tuple(ordered_keys[:subject_cap])

    state = _ProjectState(project_id=project_id, vault=root)
    state.claims = claims
    state.windows_by_key = windows_by_key
    state.authority_by_key = authority_by_key
    state.keys = capped_keys
    state.freshness_by_source = freshness
    state.conflicts_by_claim = conflicts
    state.inspected = tuple(sorted(set(inspected)))
    return state


# ---------------------------------------------------------------------------
# Per-cell projection (reuses Core temporal / authority / freshness / conflict)
# ---------------------------------------------------------------------------


def _value_sketch(value: str) -> str:
    if scan_text(value):
        return _REDACTED_SKETCH
    text = value.strip()
    if len(text) > _VALUE_SKETCH_MAX:
        return text[: _VALUE_SKETCH_MAX - 1] + "…"
    return text


def _authority_role_for(
    auth: dict[str, Any] | None, selected_claim_id: str
) -> tuple[str | None, AuthorityRole]:
    if auth is None:
        return None, "unknown"
    disposition = str(auth.get("disposition") or "").strip() or None
    competing = {str(c) for c in auth.get("competing_claim_ids") or []}
    subordinate = {str(c) for c in auth.get("subordinate_claim_ids") or []}
    auth_claim = str(auth.get("authoritative_claim_id") or "").strip()
    role: AuthorityRole
    if disposition == "authoritative" and auth_claim == selected_claim_id:
        role = "authoritative"
    elif selected_claim_id in competing:
        role = "competing"
    elif selected_claim_id in subordinate:
        role = "subordinate"
    elif disposition == "authority-pending":
        role = "authority-pending"
    else:
        role = "known-nonwinner"
    return disposition, role


def _freshness_for(source_ids: tuple[str, ...], freshness_map: dict[str, str]) -> str:
    observed = [
        freshness_map[sid] for sid in source_ids if sid in freshness_map
    ]
    if not observed:
        return "unknown"
    # Conservative: never launder stale/unknown into fresh (stale > unknown > fresh).
    return max(observed, key=lambda label: _FRESHNESS_RANK.get(label, 1))


def _evaluate_cell(
    state: _ProjectState,
    key: tuple[str, str],
    reference: str,
    anchor: CompatibilityAnchor,
) -> _Cell:
    subject, field_name = key
    windows = state.windows_by_key.get(key, [])
    if not windows:
        # Missing temporal data → honest unknown; never invent a current.
        return _Cell(
            subject=subject,
            field=field_name,
            disposition="unknown",
            selected_claim_id=None,
            value=None,
            authority_disposition=None,
            authority_role="unknown",
            freshness="unknown",
            conflict_state="unknown",
            reason="temporal-data-missing",
        )

    result = evaluate_as_of(
        list(windows),
        as_of_valid_time=reference,
        subject=subject,
        field=field_name,
        anchor=anchor,
    )
    status = str(result["status"])
    candidates = tuple(str(c) for c in result.get("candidate_claim_ids") or [])

    if status == "selected":
        selected = str(result["selected_claim_id"])
        info = state.claims.get(selected)
        value = info.value if info else None
        source_ids = info.source_ids if info else ()
        disposition, role = _authority_role_for(
            state.authority_by_key.get(key), selected
        )
        freshness = _freshness_for(source_ids, state.freshness_by_source)
        conflict_ids = tuple(state.conflicts_by_claim.get(selected, ()))
        conflict_state = "unresolved" if conflict_ids else "none"
        return _Cell(
            subject=subject,
            field=field_name,
            disposition="selected",
            selected_claim_id=selected,
            value=value,
            authority_disposition=disposition,
            authority_role=role,
            freshness=freshness,
            conflict_state=conflict_state,
            reason=str(result.get("rationale") or "selected"),
            conflict_ids=conflict_ids,
            candidate_claim_ids=candidates,
        )

    if status == "not_found":
        disposition_label = "not_found"
        reason = str(result.get("rationale") or "no-window-covers-reference")
    elif status == "unresolved_overlap":
        disposition_label = "unresolved"
        reason = "unresolved_overlap"
    elif status == "unresolved_incomplete":
        disposition_label = "unresolved"
        reason = "unresolved_incomplete"
    else:  # rejected_malformed (per-key window integrity)
        disposition_label = "unresolved"
        reason = "rejected_malformed"

    return _Cell(
        subject=subject,
        field=field_name,
        disposition=disposition_label,
        selected_claim_id=None,
        value=None,
        authority_disposition=None,
        authority_role="unknown",
        freshness="unknown",
        conflict_state="unknown" if disposition_label != "not_found" else "none",
        reason=reason,
        candidate_claim_ids=candidates,
    )


def _reference_malformed(reference: str, anchor: CompatibilityAnchor) -> bool:
    """Probe the declared valid-time via Core parsing (wall-clock ≠ valid-time)."""
    try:
        evaluate_as_of(
            [],
            as_of_valid_time=reference,
            subject="kdiff-probe",
            field="kdiff-probe",
            anchor=anchor,
        )
    except BitemporalError:
        return True
    return False


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _cell_to_json(cell: _Cell) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subject": cell.subject,
        "field": cell.field,
        "disposition": cell.disposition,
        "selected_claim_id": cell.selected_claim_id,
        "authority_disposition": cell.authority_disposition,
        "authority_role": cell.authority_role,
        "freshness": cell.freshness,
        "conflict_state": cell.conflict_state,
        "reason": cell.reason,
    }
    if cell.value is not None:
        payload["value_sketch"] = _value_sketch(cell.value)
    if cell.conflict_ids:
        payload["conflict_ids"] = list(cell.conflict_ids)
    if cell.candidate_claim_ids:
        payload["candidate_claim_ids"] = list(cell.candidate_claim_ids)
    return payload


def snapshot_to_json(payload: dict[str, Any]) -> str:
    """Deterministic serialization (NFR-001 — no wall-clock; sort_keys)."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


diff_to_json = snapshot_to_json


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _normalize_cap(subject_cap: int) -> int:
    if isinstance(subject_cap, bool) or not isinstance(subject_cap, int):
        raise KnowledgeDiffError(f"kdiff-subject-cap-invalid:{subject_cap!r}")
    if subject_cap < 1 or subject_cap > MAX_SUBJECT_CAP:
        raise KnowledgeDiffError(f"kdiff-subject-cap-out-of-range:{subject_cap}")
    return subject_cap


def _normalize_compilation(knowledge_compilation_id: str | None) -> str | None:
    if knowledge_compilation_id is None:
        return None
    token = knowledge_compilation_id.strip()
    return token or None


def read_as_of(
    vault: Path,
    *,
    project_id: str,
    as_of_valid_time: str,
    knowledge_compilation_id: str | None = None,
    subject_cap: int = DEFAULT_SUBJECT_CAP,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Read the as-of knowledge state for a project (read-only, deterministic)."""
    project = _validate_project_id(project_id)
    cap = _normalize_cap(subject_cap)
    compilation = _normalize_compilation(knowledge_compilation_id)
    resolved_anchor = anchor or require_compatibility_anchor()

    state = _load_state(
        vault,
        project,
        knowledge_compilation_id=compilation,
        subject_cap=cap,
    )

    truncated = _universe_truncated(state, cap)

    if _reference_malformed(as_of_valid_time, resolved_anchor):
        return _finish_as_of(
            project=project,
            reference=as_of_valid_time,
            compilation=compilation,
            cap=cap,
            cells=[],
            unresolved=[],
            inspected=state.inspected,
            status="rejected_malformed",
            truncated=truncated,
        )

    cells = [
        _evaluate_cell(state, key, as_of_valid_time, resolved_anchor)
        for key in state.keys
    ]
    unresolved = [
        {"subject": c.subject, "field": c.field, "reason": c.reason}
        for c in cells
        if c.disposition in ("unresolved", "unknown")
    ]
    if any(c.disposition == "selected" for c in cells):
        status = "partial" if unresolved else "ok"
    elif cells:
        status = "partial" if unresolved else "not_found"
    else:
        status = "ok"

    return _finish_as_of(
        project=project,
        reference=as_of_valid_time,
        compilation=compilation,
        cap=cap,
        cells=cells,
        unresolved=unresolved,
        inspected=state.inspected,
        status=status,
        truncated=truncated,
    )


def _universe_truncated(state: _ProjectState, cap: int) -> bool:
    total = len(set(state.windows_by_key) | set(state.authority_by_key))
    return total > cap


def _finish_as_of(
    *,
    project: str,
    reference: str,
    compilation: str | None,
    cap: int,
    cells: list[_Cell],
    unresolved: list[dict[str, Any]],
    inspected: tuple[str, ...],
    status: str,
    truncated: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "artifact_kind": AS_OF_KIND,
        "scope": {"kind": "project", "id": project},
        "as_of_valid_time": reference,
        "knowledge_compilation_id": compilation,
        "status": status,
        "cells": [_cell_to_json(c) for c in cells],
        "cell_count": len(cells),
        "truncated": truncated,
        "unresolved": sorted(
            unresolved, key=lambda u: (u["subject"], u["field"], u["reason"])
        ),
        "caps": {"subject_cap": cap},
        "inspected_artifacts": list(inspected),
        "authority": {
            "level": "derived",
            "llm_authority": False,
            "note": (
                "As-of consumes AS-2.0-TEMPORAL-001 windows + AS-CORE state; "
                "never recomputes truth or writes the vault"
            ),
        },
        "truth_boundary": TRUTH_AS_OF,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, AS_OF_KIND)
    except SchemaValidationError as exc:
        raise KnowledgeDiffError(f"kdiff-as-of-schema:{exc}") from exc
    return payload


def diff_knowledge(
    vault: Path,
    *,
    project_id: str,
    t1: str,
    t2: str,
    knowledge_compilation_id: str | None = None,
    subject_cap: int = DEFAULT_SUBJECT_CAP,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Diff the as-of knowledge state between two reference valid-times."""
    project = _validate_project_id(project_id)
    cap = _normalize_cap(subject_cap)
    compilation = _normalize_compilation(knowledge_compilation_id)
    resolved_anchor = anchor or require_compatibility_anchor()

    state = _load_state(
        vault,
        project,
        knowledge_compilation_id=compilation,
        subject_cap=cap,
    )
    truncated = _universe_truncated(state, cap)

    if _reference_malformed(t1, resolved_anchor) or _reference_malformed(
        t2, resolved_anchor
    ):
        return _finish_diff(
            project=project,
            t1=t1,
            t2=t2,
            compilation=compilation,
            cap=cap,
            buckets=_empty_buckets(),
            inspected=state.inspected,
            status="rejected_malformed",
            truncated=truncated,
        )

    buckets = _empty_buckets()
    for key in state.keys:
        cell1 = _evaluate_cell(state, key, t1, resolved_anchor)
        cell2 = _evaluate_cell(state, key, t2, resolved_anchor)
        _diff_cell(cell1, cell2, buckets)

    for name in _CHANGE_BUCKETS:
        buckets[name].sort(key=lambda r: (r["subject"], r["field"]))
    buckets["unresolved_delta"].sort(key=lambda r: (r["subject"], r["field"]))

    status = "partial" if buckets["unresolved_delta"] else "ok"
    return _finish_diff(
        project=project,
        t1=t1,
        t2=t2,
        compilation=compilation,
        cap=cap,
        buckets=buckets,
        inspected=state.inspected,
        status=status,
        truncated=truncated,
    )


_CHANGE_BUCKETS = (
    "added",
    "removed",
    "value_changed",
    "authority_changed",
    "freshness_changed",
    "conflict_changed",
)


def _empty_buckets() -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in _CHANGE_BUCKETS}
    buckets["unresolved_delta"] = []
    return buckets


def _uncertain_reason(cell1: _Cell, cell2: _Cell) -> str:
    reasons = {cell1.reason, cell2.reason}
    for priority in (
        "rejected_malformed",
        "unresolved_overlap",
        "unresolved_incomplete",
        "temporal-data-missing",
    ):
        if priority in reasons:
            return priority
    return "temporal-data-missing"


def _diff_cell(
    cell1: _Cell, cell2: _Cell, buckets: dict[str, list[dict[str, Any]]]
) -> None:
    subject, field_name = cell1.subject, cell1.field
    if cell1.disposition not in _DEFINITE or cell2.disposition not in _DEFINITE:
        # Honest unknown either side → never invent added/removed/changed.
        buckets["unresolved_delta"].append(
            {
                "subject": subject,
                "field": field_name,
                "reason": _uncertain_reason(cell1, cell2),
            }
        )
        return

    s1 = cell1.disposition == "selected"
    s2 = cell2.disposition == "selected"
    if not s1 and not s2:
        return  # both not_found — nothing valid at either reference
    if not s1 and s2:
        entry: dict[str, Any] = {
            "subject": subject,
            "field": field_name,
            "to_claim_id": cell2.selected_claim_id,
        }
        if cell2.value is not None:
            entry["value_sketch"] = _value_sketch(cell2.value)
        buckets["added"].append(entry)
        return
    if s1 and not s2:
        removed: dict[str, Any] = {
            "subject": subject,
            "field": field_name,
            "from_claim_id": cell1.selected_claim_id,
        }
        if cell1.value is not None:
            removed["value_sketch"] = _value_sketch(cell1.value)
        buckets["removed"].append(removed)
        return

    # Both selected → report every dimension that changed (may be several).
    if cell1.selected_claim_id != cell2.selected_claim_id or cell1.value != cell2.value:
        changed: dict[str, Any] = {
            "subject": subject,
            "field": field_name,
            "from_claim_id": cell1.selected_claim_id,
            "to_claim_id": cell2.selected_claim_id,
        }
        if cell1.value is not None:
            changed["from_value_sketch"] = _value_sketch(cell1.value)
        if cell2.value is not None:
            changed["to_value_sketch"] = _value_sketch(cell2.value)
        buckets["value_changed"].append(changed)
    if (
        cell1.authority_role != cell2.authority_role
        or cell1.authority_disposition != cell2.authority_disposition
    ):
        buckets["authority_changed"].append(
            {
                "subject": subject,
                "field": field_name,
                "from_role": cell1.authority_role,
                "to_role": cell2.authority_role,
                "from_disposition": cell1.authority_disposition,
                "to_disposition": cell2.authority_disposition,
            }
        )
    if cell1.freshness != cell2.freshness:
        buckets["freshness_changed"].append(
            {
                "subject": subject,
                "field": field_name,
                "from_freshness": cell1.freshness,
                "to_freshness": cell2.freshness,
            }
        )
    if cell1.conflict_state != cell2.conflict_state:
        conflict_ids = sorted(set(cell1.conflict_ids) | set(cell2.conflict_ids))
        entry_c: dict[str, Any] = {
            "subject": subject,
            "field": field_name,
            "from_state": cell1.conflict_state,
            "to_state": cell2.conflict_state,
        }
        if conflict_ids:
            entry_c["conflict_ids"] = conflict_ids
        buckets["conflict_changed"].append(entry_c)


def _finish_diff(
    *,
    project: str,
    t1: str,
    t2: str,
    compilation: str | None,
    cap: int,
    buckets: dict[str, list[dict[str, Any]]],
    inspected: tuple[str, ...],
    status: str,
    truncated: bool,
) -> dict[str, Any]:
    change_count = sum(len(buckets[name]) for name in _CHANGE_BUCKETS)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "artifact_kind": DIFF_KIND,
        "scope": {"kind": "project", "id": project},
        "t1_valid_time": t1,
        "t2_valid_time": t2,
        "knowledge_compilation_id": compilation,
        "status": status,
        "added": buckets["added"],
        "removed": buckets["removed"],
        "value_changed": buckets["value_changed"],
        "authority_changed": buckets["authority_changed"],
        "freshness_changed": buckets["freshness_changed"],
        "conflict_changed": buckets["conflict_changed"],
        "unresolved_delta": buckets["unresolved_delta"],
        "change_count": change_count,
        "caps": {"subject_cap": cap},
        "truncated": truncated,
        "inspected_artifacts": list(inspected),
        "authority": {
            "level": "derived",
            "llm_authority": False,
            "note": (
                "Diff is a derived delta over persisted state; never authority, "
                "never a Layer B mutation, never wall-clock now"
            ),
        },
        "truth_boundary": TRUTH_DIFF,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, DIFF_KIND)
    except SchemaValidationError as exc:
        raise KnowledgeDiffError(f"kdiff-diff-schema:{exc}") from exc
    return payload
