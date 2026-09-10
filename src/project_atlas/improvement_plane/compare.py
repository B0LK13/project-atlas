"""Compare two improvement-plane report snapshots."""

from __future__ import annotations

from typing import Any


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
            # Prefer owner backlog IDs when present; keep waiting marker too.
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


def _fingerprint(obs: dict[str, Any]) -> tuple[Any, ...]:
    """Identity-relevant fingerprint; ignores timestamps and ordering noise."""
    return (
        obs.get("kind"),
        obs.get("failure_class"),
        obs.get("classification"),
        obs.get("summary"),
        obs.get("open_occurrences"),
    )


def compare_reports(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    before_label: str,
    after_label: str,
) -> dict[str, Any]:
    """Compare two explicit snapshots.

    Disappearing evidence is classified ``unobservable``, not resolved.
    """
    left = _observation_map(before)
    right = _observation_map(after)

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

    # Without positive resolution evidence, absence is unobservable.
    unobservable = [
        {
            "id": oid,
            "before": left[oid],
            "disposition": "unobservable",
            "note": (
                "Observation absent in after snapshot; disappearing evidence is not "
                "proof the blocker was resolved."
            ),
        }
        for oid in gone_ids
    ]

    return {
        "schema": "atlas.improvement-plane.compare.v1",
        "package_id": "AS-IMPR-PLANE-001",
        "before_label": before_label,
        "after_label": after_label,
        "counts": {
            "new": len(new_ids),
            "persistent": len(persistent),
            "changed": len(changed),
            "unobservable": len(unobservable),
            "resolved_proven": 0,
        },
        "new": [{"id": oid, "after": right[oid]} for oid in new_ids],
        "persistent": persistent,
        "changed": changed,
        "unobservable": unobservable,
        "resolved": [],
        "honesty": {
            "disappearing_ne_resolved": True,
            "ordering_insensitive": True,
            "timestamp_noise_ignored_for_identity": True,
            "authority": "none",
        },
        "note": (
            "resolved_proven stays empty unless an explicit outcome annotation "
            "or positive resolution record is supplied; compare alone never invents resolution."
        ),
    }
