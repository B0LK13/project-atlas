"""Evaluate recorded outcomes against a later observation report."""

from __future__ import annotations

from typing import Any

from project_atlas.improvement_plane.compare import _observation_map


def evaluate_outcomes(
    *,
    before_report: dict[str, Any],
    after_report: dict[str, Any],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare annotations with later observations.

    Distinguishes improved / persisted / regressed / cannot_assess.
    Association only; no causation or time-saved claims.
    """
    before = _observation_map(before_report)
    after = _observation_map(after_report)

    # Latest annotation wins per recommendation_id.
    latest: dict[str, dict[str, Any]] = {}
    for row in outcomes:
        rid = row.get("recommendation_id")
        if isinstance(rid, str) and rid.strip():
            latest[rid] = row

    evaluations: list[dict[str, Any]] = []
    for rid, outcome in sorted(latest.items()):
        status = outcome.get("status")
        # Map recommendation ids to observation ids when they embed them.
        obs_id = rid
        if rid.startswith("rec:"):
            obs_id = rid[4:]
        before_obs = before.get(obs_id)
        after_obs = after.get(obs_id)

        if before_obs is None and after_obs is None:
            result = "cannot_assess"
            detail = "Observation id not present in before or after snapshots."
        elif before_obs is not None and after_obs is None:
            # Disappearance without positive resolution evidence.
            if status == "completed":
                result = "cannot_assess"
                detail = (
                    "Annotated completed, but after snapshot lacks the observation; "
                    "disappearance is not proof of resolution."
                )
            else:
                result = "cannot_assess"
                detail = "Observation unobservable in after snapshot."
        elif before_obs is None and after_obs is not None:
            result = "regressed"
            detail = "Observation absent before but present after (new/reopened)."
        else:
            # both present
            if status in {"completed", "accepted"} and after_obs is not None:
                result = "persisted"
                detail = (
                    "Annotated as "
                    f"{status}, but observation remains present after; "
                    "association only, not causation."
                )
            elif status == "deferred":
                result = "persisted" if after_obs is not None else "cannot_assess"
                detail = "Deferred annotation; observation still tracked or unobservable."
            elif status == "attempted":
                result = "persisted"
                detail = "Attempted annotation with observation still present afterward."
            else:
                result = "cannot_assess"
                detail = f"Unhandled outcome status {status!r}."

        evaluations.append(
            {
                "recommendation_id": rid,
                "outcome_status": status,
                "observation_id": obs_id,
                "result": result,
                "detail": detail,
                "evidence_refs": list(outcome.get("evidence_refs") or []),
                "before_present": before_obs is not None,
                "after_present": after_obs is not None,
            }
        )

    counts = {
        "improved": 0,
        "persisted": 0,
        "regressed": 0,
        "cannot_assess": 0,
    }
    for row in evaluations:
        key = str(row["result"])
        if key in counts:
            counts[key] += 1

    return {
        "schema": "atlas.improvement-plane.evaluation.v1",
        "package_id": "AS-IMPR-PLANE-001",
        "sample_size": len(evaluations),
        "counts": counts,
        "evaluations": evaluations,
        "honesty": {
            "association_ne_causation": True,
            "time_saved_claimed": False,
            "disappearing_ne_resolved": True,
            "authority": "none",
            "dag_gate_resolved": False,
        },
        "note": (
            "Evaluation reports association between annotations and later observations. "
            "It does not claim causal productivity improvement or time saved."
        ),
    }
