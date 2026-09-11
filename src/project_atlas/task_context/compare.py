"""Compare two task-context packet versions."""

from __future__ import annotations

from typing import Any

from project_atlas.task_context.models import TaskContextPacket


def compare_packets(left: TaskContextPacket, right: TaskContextPacket) -> dict[str, Any]:
    left_frags = {f.fragment_id: f for f in left.fragments}
    right_frags = {f.fragment_id: f for f in right.fragments}
    added = sorted(set(right_frags) - set(left_frags))
    removed = sorted(set(left_frags) - set(right_frags))
    changed_sources: list[dict[str, Any]] = []
    for fid in sorted(set(left_frags) & set(right_frags)):
        a, b = left_frags[fid], right_frags[fid]
        a_id = a.source_identity.identity if a.source_identity else None
        b_id = b.source_identity.identity if b.source_identity else None
        if a.body != b.body or a_id != b_id or a.included != b.included:
            changed_sources.append(
                {
                    "fragment_id": fid,
                    "path": b.source_path or a.source_path,
                    "body_changed": a.body != b.body,
                    "identity_changed": a_id != b_id,
                    "inclusion_changed": a.included != b.included,
                    "left_identity": a_id,
                    "right_identity": b_id,
                }
            )

    contract_changed = left.contract.contract_digest != right.contract.contract_digest
    req_changed = left.contract.requirement_ids != right.contract.requirement_ids or (
        left.contract.objective != right.contract.objective
    )

    left_u = {u.uncertainty_id: u for u in left.uncertainties}
    right_u = {u.uncertainty_id: u for u in right.uncertainties}
    new_uncertainties = [
        right_u[uid].model_dump(mode="json") for uid in sorted(set(right_u) - set(left_u))
    ]

    budget_exclusions = []
    if right.budget_report:
        for part in right.budget_report.parts:
            if not part.included and part.exclusion_reason and "budget" in part.exclusion_reason:
                budget_exclusions.append(
                    {
                        "part_id": part.part_id,
                        "reason": part.exclusion_reason,
                        "chars": part.chars,
                    }
                )

    return {
        "left_packet_id": left.packet_id,
        "right_packet_id": right.packet_id,
        "left_content_digest": left.content_digest,
        "right_content_digest": right.content_digest,
        "contract_requirements_changed": contract_changed or req_changed,
        "contract": {
            "left": left.contract.model_dump(mode="json"),
            "right": right.contract.model_dump(mode="json"),
        },
        "added_fragments": added,
        "removed_fragments": removed,
        "changed_source_fragments": changed_sources,
        "new_uncertainties": new_uncertainties,
        "budget_exclusions_on_right": budget_exclusions,
    }
