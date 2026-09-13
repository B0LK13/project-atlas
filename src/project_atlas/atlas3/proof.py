"""AT3-050 — Agent proof-of-work.

MODEL CLAIM OF COMPLETION != PROOF.
Evidence chain: TASK → IMPLEMENTATION → TESTS → CI → IV → ADV → INTEGRATION → POST-MERGE.
"""

from __future__ import annotations

import json
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    GENERATOR_ID,
    OPS_RELATIVE,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
    require_project,
    require_vault,
    write_json_atomic,
)

PACKAGE_ID: Final[str] = "AT3-050"
PROOF_STAGES: Final[tuple[str, ...]] = (
    "TASK",
    "IMPLEMENTATION",
    "TESTS",
    "CI",
    "INDEPENDENT_VERIFICATION",
    "ADV",
    "INTEGRATION",
    "POST_MERGE",
)


def evaluate_proof(
    vault: Any,
    task_id: str,
    *,
    project_id: str,
    evidence: dict[str, Any] | None = None,
    model_claims_complete: bool = False,
) -> dict[str, Any]:
    """Evaluate a proof chain. Missing stages stay UNKNOWN. Model claim never proves."""
    root = require_vault(vault)
    tid = task_id.strip()
    if not tid or "/" in tid or "\\" in tid or tid in {".", ".."}:
        raise Atlas3Error("UNSAFE_TASK_ID", f"unsafe task id: {task_id!r}")
    pid = require_project(root, project_id)
    path = root / OPS_RELATIVE / "proof" / f"{tid}.json"
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise Atlas3Error("PROOF_CORRUPT", "proof artifact is not readable JSON") from exc
        if not isinstance(existing, dict):
            raise Atlas3Error("PROOF_CORRUPT", "proof artifact must be an object")
        prior = existing.get("project_id")
        if prior is not None and str(prior) != pid:
            raise Atlas3Error(
                "PROJECT_MISMATCH",
                f"proof {tid!r} already bound to project {prior!r}",
            )
    supplied = evidence or {}
    stages: dict[str, Any] = {}
    present = 0
    for name in PROOF_STAGES:
        raw = supplied.get(name)
        if isinstance(raw, dict) and raw.get("evidence_ref"):
            stages[name] = {
                "status": "PRESENT",
                "evidence_ref": str(raw["evidence_ref"]),
                "authority": "derived",
            }
            present += 1
        else:
            stages[name] = {
                "status": "UNKNOWN",
                "reason": "no independent evidence_ref",
                "authority": "none",
            }

    if present == len(PROOF_STAGES):
        chain_status = "PROVEN"
    elif present == 0:
        chain_status = "UNKNOWN"
    else:
        chain_status = "PARTIAL"

    if model_claims_complete and chain_status != "PROVEN":
        chain_status = "UNPROVEN_MODEL_CLAIM"

    report = {
        "schema": "atlas3.agent-proof.v1",
        "schema_version": 1,
        "package": PACKAGE_ID,
        "task_id": tid,
        "project_id": pid,
        "stages": stages,
        "present_count": present,
        "chain_status": chain_status,
        "model_claims_complete": model_claims_complete,
        "model_claim_is_proof": False,
        "merge_authorization": "NOT_GRANTED",
        "authority": "derived",
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
        "generated": {"by": GENERATOR_ID},
    }
    write_json_atomic(path, report)
    return report
