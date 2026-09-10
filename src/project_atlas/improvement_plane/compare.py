"""Compare two improvement-plane report snapshots."""

from __future__ import annotations

from typing import Any

from project_atlas.improvement_plane.errors import ImprovementPlaneError


def _snapshot_compat(report: object, *, label: str) -> dict[str, Any]:
    """Return compatibility assessment for a compare input."""
    if not isinstance(report, dict):
        return {
            "label": label,
            "status": "incompatible",
            "reason": "not-a-json-object",
        }
    schema = report.get("schema")
    panels = report.get("panels")
    if not isinstance(panels, dict):
        return {
            "label": label,
            "status": "incomplete",
            "reason": "missing-panels-object",
            "schema": schema,
        }
    required = (
        "owner_action_backlog",
        "recurring_failures",
        "waiting_work",
    )
    missing = [name for name in required if name not in panels]
    if missing:
        return {
            "label": label,
            "status": "incomplete",
            "reason": "missing-required-panels",
            "missing_panels": missing,
            "schema": schema,
        }
    if (
        isinstance(schema, str)
        and schema.startswith("atlas.")
        and "improvement-plane.report" not in schema
    ):
        return {
            "label": label,
            "status": "incompatible",
            "reason": "foreign-schema",
            "schema": schema,
        }
    return {"label": label, "status": "ok", "schema": schema}


def _observation_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract stable observation IDs from a compiled report."""
    panels = report.get("panels") or {}
    observations: dict[str, dict[str, Any]] = {}

    for item in (panels.get("owner_action_backlog") or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        oid = f"owner:{item.get('node_id')}"
        observations[oid] = {
            "id": oid,
            "kind": "owner_decision",
            "summary": item.get("description") or item.get("next_required_owner_action"),
            "sources": [item.get("source")],
            "status": "open",
        }

    for item in (panels.get("recurring_failures") or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        oid = f"finding:{item.get('finding_id')}"
        observations[oid] = {
            "id": oid,
            "kind": "engineering_failure",
            "summary": f"{item.get('finding_id')} class={item.get('failure_class')}",
            "sources": list(item.get("sources") or []),
            "status": "open",
            "failure_class": item.get("failure_class"),
            "open_occurrences": item.get("open_occurrences"),
        }

    for item in (panels.get("waiting_work") or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        classification = item.get("classification")
        if classification in {"BLOCKED_EXTERNAL"}:
            oid = f"external:{item.get('id')}"
            kind = "external_dependency"
        elif classification in {"READY", "DERIVABLE"}:
            oid = f"queue:{classification}:{item.get('id')}"
            kind = "queued_opportunity"
        elif classification in {"BLOCKED_BY_OWNER", "WAITING_OWNER"}:
            oid = f"waiting:{classification}:{item.get('id')}"
            kind = "owner_decision"
        else:
            oid = f"waiting:{classification}:{item.get('id')}"
            kind = "waiting"
        observations[oid] = {
            "id": oid,
            "kind": kind,
            "summary": item.get("summary") or classification,
            "sources": [item.get("source")],
            "status": "open",
            "classification": classification,
        }

    for item in (panels.get("data_quality_risks") or {}).get("contradictory_status") or []:
        if not isinstance(item, dict):
            continue
        oid = f"quality:contradictory:{item.get('finding_id')}"
        observations[oid] = {
            "id": oid,
            "kind": "data_quality",
            "summary": f"contradictory statuses for {item.get('finding_id')}",
            "sources": list(item.get("sources") or []),
            "status": "open",
        }

    return observations


def _closed_finding_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    panels = report.get("panels") or {}
    closed: dict[str, dict[str, Any]] = {}
    for item in (panels.get("closed_findings") or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        fid = item.get("finding_id")
        if not fid:
            continue
        oid = f"finding:{fid}"
        closed[oid] = {
            "id": oid,
            "sources": list(item.get("sources") or []),
            "statuses": list(item.get("statuses") or []),
        }
    return closed


def _fingerprint(obs: dict[str, Any]) -> tuple[Any, ...]:
    """Identity-relevant fingerprint; ignores timestamps and ordering noise."""
    return (
        obs.get("kind"),
        obs.get("failure_class"),
        obs.get("classification"),
        obs.get("summary"),
        obs.get("open_occurrences"),
    )


def render_compare_summary(result: dict[str, Any]) -> str:
    lines = [
        "# AS-IMPR-PLANE-001 — Snapshot compare",
        "",
        f"- Before: `{result.get('before_label')}`",
        f"- After: `{result.get('after_label')}`",
        f"- Comparison status: `{result.get('comparison_status')}`",
        f"- Counts: {result.get('counts')}",
        "",
        "Honesty: disappearance ≠ resolved without positive closed-finding evidence.",
        "",
    ]
    if result.get("comparison_status") != "ok":
        lines.append(f"Issue: {result.get('comparison_issue')}")
        return "\n".join(lines) + "\n"
    for label in ("resolved", "new", "changed", "persistent", "unobservable"):
        rows = result.get(label) or []
        lines.append(f"## {label} ({len(rows)})")
        for row in rows[:8]:
            lines.append(f"- `{row.get('id')}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def compare_reports(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    before_label: str,
    after_label: str,
) -> dict[str, Any]:
    """Compare two explicit snapshots.

    Disappearing evidence is ``unobservable`` unless the after snapshot carries
    explicit closed-finding evidence for the same stable id.
    """
    before_compat = _snapshot_compat(before, label=before_label)
    after_compat = _snapshot_compat(after, label=after_label)
    statuses = {before_compat["status"], after_compat["status"]}
    empty_counts = {
        "new": 0,
        "persistent": 0,
        "changed": 0,
        "unobservable": 0,
        "resolved": 0,
    }
    honesty = {
        "disappearing_ne_resolved": True,
        "ordering_insensitive": True,
        "timestamp_noise_ignored_for_identity": True,
        "authority": "none",
    }
    if "incompatible" in statuses:
        return {
            "schema": "atlas.improvement-plane.compare.v1",
            "package_id": "AS-IMPR-PLANE-001",
            "before_label": before_label,
            "after_label": after_label,
            "comparison_status": "incompatible",
            "comparison_issue": {"before": before_compat, "after": after_compat},
            "counts": empty_counts,
            "new": [],
            "persistent": [],
            "changed": [],
            "unobservable": [],
            "resolved": [],
            "honesty": honesty,
            "note": "Comparison refused: one or both inputs are incompatible.",
        }
    if "incomplete" in statuses:
        return {
            "schema": "atlas.improvement-plane.compare.v1",
            "package_id": "AS-IMPR-PLANE-001",
            "before_label": before_label,
            "after_label": after_label,
            "comparison_status": "incomplete",
            "comparison_issue": {"before": before_compat, "after": after_compat},
            "counts": empty_counts,
            "new": [],
            "persistent": [],
            "changed": [],
            "unobservable": [],
            "resolved": [],
            "honesty": honesty,
            "note": "Comparison incomplete: required panels missing on one or both inputs.",
        }

    left = _observation_map(before)
    right = _observation_map(after)
    closed_after = _closed_finding_map(after)

    new_ids = sorted(set(right) - set(left))
    gone_ids = sorted(set(left) - set(right))
    shared = sorted(set(left) & set(right))

    persistent: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for oid in shared:
        a = left[oid]
        b = right[oid]
        if _fingerprint(a) == _fingerprint(b):
            persistent.append({"id": oid, "before": a, "after": b})
        else:
            changed.append({"id": oid, "before": a, "after": b})

    resolved: list[dict[str, Any]] = []
    unobservable: list[dict[str, Any]] = []
    for oid in gone_ids:
        if oid in closed_after:
            resolved.append(
                {
                    "id": oid,
                    "before": left[oid],
                    "disposition": "resolved",
                    "resolution_evidence": closed_after[oid],
                    "note": (
                        "Resolved because after snapshot includes explicit "
                        "closed-finding evidence for this id."
                    ),
                }
            )
        else:
            unobservable.append(
                {
                    "id": oid,
                    "before": left[oid],
                    "disposition": "unobservable",
                    "note": (
                        "Observation absent in after snapshot; disappearing evidence is not "
                        "proof the blocker was resolved."
                    ),
                }
            )

    return {
        "schema": "atlas.improvement-plane.compare.v1",
        "package_id": "AS-IMPR-PLANE-001",
        "before_label": before_label,
        "after_label": after_label,
        "comparison_status": "ok",
        "comparison_issue": None,
        "counts": {
            "new": len(new_ids),
            "persistent": len(persistent),
            "changed": len(changed),
            "unobservable": len(unobservable),
            "resolved": len(resolved),
        },
        "new": [{"id": oid, "after": right[oid]} for oid in new_ids],
        "persistent": persistent,
        "changed": changed,
        "unobservable": unobservable,
        "resolved": resolved,
        "honesty": honesty,
        "note": (
            "resolved requires explicit closed-finding evidence in the after snapshot; "
            "compare never invents resolution from absence alone."
        ),
    }


def require_compareable_reports(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    before_label: str,
    after_label: str,
) -> None:
    """Raise operator-facing error for hard-incompatible compare inputs."""
    result = compare_reports(
        before, after, before_label=before_label, after_label=after_label
    )
    if result["comparison_status"] == "incompatible":
        raise ImprovementPlaneError(
            "compare-incompatible",
            f"Cannot compare incompatible snapshots: {before_label} vs {after_label}",
        )
