"""AS-QUERY-MULTI-001 tip-safe multi-subject / multi-project query PLAN helpers.

Planning-only surface over Core QUERY planes (point / multifield / list).
Plan ≠ answer ≠ authority winner ≠ temporal tip ≠ trust score ≠ graph subject.

Does not write the vault. Does not call knowledge_compiler / authority /
temporal evaluators. Does not mutate AS-QUERY-001 --list semantics.
Optional CLI plan dump is intentionally deferred (serialize vs other cli.py writers).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.secrets import scan_text

PACKAGE_ID = "AS-QUERY-MULTI-001"
PLAN_KIND = "multi_query_plan"
SCHEMA_KIND = "query-multi-plan"
SCHEMA_VERSION = 1

QueryShapeName = Literal["point", "multifield", "list"]
QueryKindName = Literal["authoritative", "temporal", "explain"]

ALLOWED_SHAPES: frozenset[str] = frozenset({"point", "multifield", "list"})
ALLOWED_KINDS: frozenset[str] = frozenset({"authoritative", "temporal", "explain"})

# Fail-closed caps (QM-FR-009 / oversized batches).
MAX_PROJECTS = 64
MAX_ITEMS_PER_PROJECT = 256
MAX_ITEMS_TOTAL = 512

_SAFE_REDACTED_NOTE = "plan note redacted (secret-shaped content)"
_FORBIDDEN_PLAN_KEYS: frozenset[str] = frozenset(
    {
        "trust",
        "trust_score",
        "confidence",
        "confidence_score",
        "value",
        "claim_id",
        "authority_disposition",
        "graph_id",
        "graph_subject",
        "resolved_entity_id",
        "global_entity_id",
        "answer",
        "answers",
        "outcome_class",
    }
)


class QueryPlanError(ValueError):
    """Fail-closed plan rejection (request_invalid class)."""

    def __init__(
        self,
        message: str,
        *,
        invalid_items: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        self.code = "request_invalid"
        self.message = message
        self.invalid_items: list[dict[str, Any]] = [
            dict(item) for item in (invalid_items or ())
        ]
        super().__init__(f"{self.code}: {message}")

    def to_dict(self) -> dict[str, Any]:
        """Structured rejection envelope (never a success plan)."""
        return {
            "schema_version": SCHEMA_VERSION,
            "package": PACKAGE_ID,
            "status": self.code,
            "message": self.message,
            "invalid_items": list(self.invalid_items),
        }


def _redact_notes(notes: Sequence[str] | None) -> list[str]:
    if not notes:
        return []
    out: list[str] = []
    for note in notes:
        if not isinstance(note, str):
            raise QueryPlanError("notes entries must be strings")
        if scan_text(note):
            out.append(_SAFE_REDACTED_NOTE)
        else:
            out.append(note)
    return out


def _reject_forbidden_keys(payload: Mapping[str, Any], *, path: str) -> None:
    for key in payload:
        if key in _FORBIDDEN_PLAN_KEYS or key.startswith("graph_"):
            raise QueryPlanError(
                f"forbidden field {key!r} at {path} "
                "(plan ≠ answer/authority/graph/trust; QM-FR-007/008)",
                invalid_items=[{"path": path, "field": key, "reason": "forbidden_field"}],
            )


def _normalize_item(
    raw: Mapping[str, Any],
    *,
    project_id: str,
    index: int,
) -> dict[str, Any]:
    path = f"projects[{project_id}].items[{index}]"
    if not isinstance(raw, Mapping):
        raise QueryPlanError(
            f"plan item at {path} must be an object",
            invalid_items=[{"path": path, "reason": "not_object"}],
        )
    _reject_forbidden_keys(raw, path=path)

    shape = raw.get("shape")
    kind = raw.get("kind")
    invalid: list[dict[str, Any]] = []
    if shape not in ALLOWED_SHAPES:
        invalid.append(
            {
                "path": path,
                "field": "shape",
                "observed": shape,
                "reason": "unknown_or_missing_shape",
            }
        )
    if kind not in ALLOWED_KINDS:
        invalid.append(
            {
                "path": path,
                "field": "kind",
                "observed": kind,
                "reason": "unknown_or_missing_kind",
            }
        )
    if invalid:
        raise QueryPlanError(
            f"invalid plan item at {path}",
            invalid_items=invalid,
        )

    item: dict[str, Any] = {"shape": shape, "kind": kind}

    if shape == "point":
        subject = raw.get("subject")
        field = raw.get("field")
        if not isinstance(subject, str) or not subject.strip():
            raise QueryPlanError(
                f"point item at {path} requires non-empty subject",
                invalid_items=[{"path": path, "field": "subject", "reason": "missing"}],
            )
        if not isinstance(field, str) or not field.strip():
            raise QueryPlanError(
                f"point item at {path} requires non-empty field",
                invalid_items=[{"path": path, "field": "field", "reason": "missing"}],
            )
        if "fields" in raw:
            raise QueryPlanError(
                f"point item at {path} must not include fields",
                invalid_items=[{"path": path, "field": "fields", "reason": "unexpected"}],
            )
        item["subject"] = subject.strip()
        item["field"] = field.strip()
    elif shape == "multifield":
        subject = raw.get("subject")
        fields = raw.get("fields")
        if not isinstance(subject, str) or not subject.strip():
            raise QueryPlanError(
                f"multifield item at {path} requires non-empty subject",
                invalid_items=[{"path": path, "field": "subject", "reason": "missing"}],
            )
        if not isinstance(fields, Sequence) or isinstance(fields, (str, bytes)):
            raise QueryPlanError(
                f"multifield item at {path} requires non-empty fields list",
                invalid_items=[{"path": path, "field": "fields", "reason": "missing"}],
            )
        if "field" in raw:
            raise QueryPlanError(
                f"multifield item at {path} must not include field",
                invalid_items=[{"path": path, "field": "field", "reason": "unexpected"}],
            )
        normalized_fields: list[str] = []
        seen: set[str] = set()
        for field_name in fields:
            if not isinstance(field_name, str) or not field_name.strip():
                raise QueryPlanError(
                    f"multifield item at {path} has empty field name",
                    invalid_items=[
                        {"path": path, "field": "fields", "reason": "empty_field_name"}
                    ],
                )
            name = field_name.strip()
            if name in seen:
                raise QueryPlanError(
                    f"multifield item at {path} has duplicate field {name!r}",
                    invalid_items=[
                        {
                            "path": path,
                            "field": "fields",
                            "observed": name,
                            "reason": "duplicate_field",
                        }
                    ],
                )
            seen.add(name)
            normalized_fields.append(name)
        if not normalized_fields:
            raise QueryPlanError(
                f"multifield item at {path} requires non-empty fields list",
                invalid_items=[{"path": path, "field": "fields", "reason": "empty"}],
            )
        item["subject"] = subject.strip()
        item["fields"] = normalized_fields
    else:  # list
        for forbidden in ("subject", "field", "fields"):
            if forbidden in raw:
                raise QueryPlanError(
                    f"list item at {path} must not include {forbidden}",
                    invalid_items=[
                        {"path": path, "field": forbidden, "reason": "unexpected"}
                    ],
                )

    if "attach_explain_receipt" in raw:
        flag = raw["attach_explain_receipt"]
        if not isinstance(flag, bool):
            raise QueryPlanError(
                f"attach_explain_receipt at {path} must be boolean",
                invalid_items=[
                    {
                        "path": path,
                        "field": "attach_explain_receipt",
                        "reason": "not_boolean",
                    }
                ],
            )
        item["attach_explain_receipt"] = flag

    return item


def build_query_plan(
    projects: Sequence[Mapping[str, Any]],
    *,
    notes: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a tip-safe multi-query plan from explicit caller input.

    Ordering rule (QM-FR-011): **caller order preserved** for projects and
    for items within each project. Identical inputs → identical plan JSON.

    Fail-closed (QM-FR-009/010): any invalid item rejects the **entire** plan
    with a structured ``QueryPlanError`` listing invalids — never a success
    plan that silently drops failures.
    """
    if not projects:
        raise QueryPlanError("empty plan rejected (no projects)")
    if len(projects) > MAX_PROJECTS:
        raise QueryPlanError(
            f"plan exceeds MAX_PROJECTS={MAX_PROJECTS}",
            invalid_items=[{"reason": "oversized_projects", "count": len(projects)}],
        )

    built_projects: list[dict[str, Any]] = []
    total_items = 0
    collected_invalids: list[dict[str, Any]] = []

    for p_index, project in enumerate(projects):
        path = f"projects[{p_index}]"
        if not isinstance(project, Mapping):
            raise QueryPlanError(
                f"project scope at {path} must be an object",
                invalid_items=[{"path": path, "reason": "not_object"}],
            )
        _reject_forbidden_keys(project, path=path)
        project_id = project.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            raise QueryPlanError(
                f"project scope at {path} requires non-empty project_id",
                invalid_items=[{"path": path, "field": "project_id", "reason": "missing"}],
            )
        project_id = project_id.strip()
        items_raw = project.get("items")
        if not isinstance(items_raw, Sequence) or isinstance(items_raw, (str, bytes)):
            raise QueryPlanError(
                f"project {project_id!r} requires a non-empty items list",
                invalid_items=[
                    {
                        "path": f"{path}.items",
                        "project_id": project_id,
                        "reason": "missing_items",
                    }
                ],
            )
        if not items_raw:
            raise QueryPlanError(
                f"project {project_id!r} has empty items list",
                invalid_items=[
                    {
                        "path": f"{path}.items",
                        "project_id": project_id,
                        "reason": "empty_items",
                    }
                ],
            )
        if len(items_raw) > MAX_ITEMS_PER_PROJECT:
            raise QueryPlanError(
                f"project {project_id!r} exceeds MAX_ITEMS_PER_PROJECT="
                f"{MAX_ITEMS_PER_PROJECT}",
                invalid_items=[
                    {
                        "project_id": project_id,
                        "reason": "oversized_items",
                        "count": len(items_raw),
                    }
                ],
            )

        built_items: list[dict[str, Any]] = []
        for i_index, raw_item in enumerate(items_raw):
            try:
                built_items.append(
                    _normalize_item(raw_item, project_id=project_id, index=i_index)
                )
            except QueryPlanError as exc:
                # Accumulate then reject entire plan (QM-FR-010 / QM-ADV-002).
                collected_invalids.extend(exc.invalid_items)
                if not exc.invalid_items:
                    collected_invalids.append(
                        {
                            "path": f"projects[{project_id}].items[{i_index}]",
                            "reason": "invalid",
                            "message": exc.message,
                        }
                    )

        if collected_invalids:
            # Continue scanning remaining projects/items only to list all
            # invalids, then reject — never emit a partial success plan.
            continue

        total_items += len(built_items)
        built_projects.append({"project_id": project_id, "items": built_items})

    if collected_invalids:
        raise QueryPlanError(
            "plan rejected: one or more items invalid "
            "(no silent partial success; QM-FR-010)",
            invalid_items=collected_invalids,
        )

    if total_items > MAX_ITEMS_TOTAL:
        raise QueryPlanError(
            f"plan exceeds MAX_ITEMS_TOTAL={MAX_ITEMS_TOTAL}",
            invalid_items=[{"reason": "oversized_total", "count": total_items}],
        )

    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "package": PACKAGE_ID,
        "plan_kind": PLAN_KIND,
        "projects": built_projects,
        "notes": _redact_notes(notes),
    }
    validate_query_plan(plan)
    return plan


def validate_query_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a plan envelope (schema + tip-safe semantic guards)."""
    if not isinstance(plan, Mapping):
        raise QueryPlanError("plan must be an object")
    _reject_forbidden_keys(plan, path="<root>")
    if plan.get("package") != PACKAGE_ID:
        raise QueryPlanError("plan package must be AS-QUERY-MULTI-001")
    if plan.get("plan_kind") != PLAN_KIND:
        raise QueryPlanError("plan_kind must be multi_query_plan")
    try:
        validate_record(dict(plan), SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise QueryPlanError(str(exc)) from exc
    return dict(plan)


def plan_to_json(plan: Mapping[str, Any]) -> str:
    """Serialize a plan deterministically (sort_keys; NFR-001 — no wall-clock)."""
    validate_query_plan(plan)
    return json.dumps(dict(plan), indent=2, sort_keys=True) + "\n"


def rejection_to_json(error: QueryPlanError) -> str:
    """Serialize a structured plan rejection deterministically."""
    return json.dumps(error.to_dict(), indent=2, sort_keys=True) + "\n"
