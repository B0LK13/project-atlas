"""Evaluate recorded outcomes against a later observation report."""

from __future__ import annotations

from typing import Any

from project_atlas.improvement_plane.compare import _closed_finding_map, _observation_map


def render_evaluate_summary(result: dict[str, Any]) -> str:
    lines = [
        "# AS-IMPR-PLANE-001 — Outcome evaluation",
        "",
        f"- Sample size: {result.get('sample_size')}",
        f"- Counts: {result.get('counts')}",
        "",
        "Honesty: association ≠ causation; time saved not claimed; "
        "disappearance ≠ resolved.",
        "",
        "## Evaluations",
        "",
    ]
    for row in result.get("evaluations") or []:
        lines.append(
            f"- `{row.get('recommendation_id')}` → **{row.get('result')}** "
            f"(outcome={row.get('outcome_status')}): {row.get('detail')}"
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def evaluate_outcomes(
    *,
    before_report: dict[str, Any],
    after_report: dict[str, Any],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare annotations with later observations.

    Distinguishes improved / persisted / regressed / inconclusive.
    Association only; no causation or time-saved claims.
    """
    before = _observation_map(before_report)
    after = _observation_map(after_report)
    closed_after = _closed_finding_map(after_report)

    # Latest annotation wins per recommendation_id.
    latest: dict[str, dict[str, Any]] = {}
    for row in outcomes:
        rid = row.get("recommendation_id")
        if isinstance(rid, str) and rid.strip():
            latest[rid] = row

    evaluations: list[dict[str, Any]] = []
    for rid, outcome in sorted(latest.items()):
        status = outcome.get("status")
        obs_id = rid
        if rid.startswith("rec:"):
            obs_id = rid[4:]
        before_obs = before.get(obs_id)
        after_obs = after.get(obs_id)

        if before_obs is None and after_obs is None:
            if obs_id in closed_after and status in {"completed", "accepted"}:
                result = "improved"
                detail = (
                    "Observation absent from open panels but after snapshot includes "
                    "explicit closed-finding evidence; association only."
                )
            else:
                result = "inconclusive"
                detail = "Observation id not present in before or after open panels."
        elif before_obs is not None and after_obs is None:
            if obs_id in closed_after:
                result = "improved"
                detail = (
                    "Open observation gone and after snapshot includes closed-finding "
                    "evidence for the same id; association only, not causation."
                )
            else:
                result = "inconclusive"
                detail = (
                    "Observation unobservable in after snapshot; disappearance is not "
                    "proof of resolution even when annotated completed."
                )
        elif before_obs is None and after_obs is not None:
            result = "regressed"
            detail = "Observation absent before but present after (new/reopened)."
        else:
            # both present
            assert before_obs is not None
            assert after_obs is not None
            before_occ = before_obs.get("open_occurrences")
            after_occ = after_obs.get("open_occurrences")
            if (
                isinstance(before_occ, int)
                and isinstance(after_occ, int)
                and after_occ < before_occ
            ):
                result = "improved"
                detail = (
                    f"Open occurrences decreased {before_occ}→{after_occ} while still "
                    "present; association only."
                )
            elif (
                isinstance(before_occ, int)
                and isinstance(after_occ, int)
                and after_occ > before_occ
            ):
                result = "regressed"
                detail = (
                    f"Open occurrences increased {before_occ}→{after_occ}; "
                    "association only."
                )
            elif status in {"completed", "accepted"}:
                result = "persisted"
                detail = (
                    f"Annotated as {status}, but observation remains present after; "
                    "association only, not causation."
                )
            elif status == "deferred":
                result = "persisted"
                detail = "Deferred annotation; observation still tracked."
            elif status == "attempted":
                result = "persisted"
                detail = "Attempted annotation with observation still present afterward."
            else:
                result = "inconclusive"
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
                "closed_evidence_present": obs_id in closed_after,
            }
        )

    counts = {
        "improved": 0,
        "persisted": 0,
        "regressed": 0,
        "inconclusive": 0,
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
            "It does not claim causal productivity improvement or time saved. "
            "`inconclusive` replaces unverifiable cases (including false resolution)."
        ),
    }
