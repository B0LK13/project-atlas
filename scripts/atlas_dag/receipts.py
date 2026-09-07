"""ATLAS_IV_RECEIPT_V1 formal-IV eligibility (D-007).

A receipt satisfies the formal-IV gate for a candidate only when every check
passes. Anything else is rejected with explicit reasons (fail-closed).
"""
from __future__ import annotations

PASS_SHAPED_RESULTS = frozenset({"PASS", "PASS_WITH_FINDINGS"})


def formal_iv_status(
    receipt: dict,
    pr_head: str | None,
    pr_tree: str | None,
    approved_verifiers: set[str],
) -> tuple[bool, list[str]]:
    """Return (eligible, reasons). eligible is True only when reasons is empty."""
    reasons: list[str] = []

    if not pr_head:
        reasons.append("CANDIDATE_HEAD_UNKNOWN")
    elif receipt.get("head") != pr_head:
        reasons.append("HEAD_MISMATCH")

    if pr_tree and receipt.get("tree") != pr_tree:
        reasons.append("TREE_MISMATCH")

    if receipt.get("formal_independence") != "PASS":
        reasons.append("FORMAL_INDEPENDENCE_NOT_PASS")

    if receipt.get("candidate_author_conflict"):
        reasons.append("AUTHOR_CONFLICT")

    if receipt.get("write_activity_count", 1) != 0:
        reasons.append("WRITE_ACTIVITY_NONZERO")

    verifier = receipt.get("verifier_id", "")
    if not approved_verifiers:
        reasons.append("VERIFIER_POOL_UNDEFINED")
    elif verifier not in approved_verifiers:
        reasons.append("VERIFIER_NOT_APPROVED")

    if receipt.get("result") not in PASS_SHAPED_RESULTS:
        reasons.append(f"RESULT_NOT_PASS_SHAPED:{receipt.get('result')}")

    return (not reasons, reasons)


def latest_eligible_receipt(
    receipts: list[dict],
    pr_head: str | None,
    pr_tree: str | None,
    approved_verifiers: set[str],
) -> tuple[dict | None, dict[str, list[str]]]:
    """Pick the newest eligible receipt; return (receipt, per-receipt rejection reasons)."""
    rejected: dict[str, list[str]] = {}
    eligible: list[dict] = []
    for receipt in receipts:
        ok, why = formal_iv_status(receipt, pr_head, pr_tree, approved_verifiers)
        if ok:
            eligible.append(receipt)
        else:
            rejected[receipt["receipt_id"]] = why
    if not eligible:
        return None, rejected
    return eligible[-1], rejected
