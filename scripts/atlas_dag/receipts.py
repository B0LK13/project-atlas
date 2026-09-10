"""ATLAS_IV_RECEIPT_V1 formal-IV eligibility (D-007 + D-PR720 trust boundary).

A receipt satisfies the formal-IV gate for a candidate only when every check
passes. Anything else is rejected with explicit reasons (fail-closed):

- exact HEAD *and* exact TREE are required; an unknown candidate head/tree
  rejects the receipt (CANDIDATE_HEAD_UNKNOWN / CANDIDATE_TREE_UNKNOWN).
- self-declared receipt fields are not authenticated identity: the verifier
  must be bound in the trusted pool to a principal, and the receipt's actual
  source (GitHub comment author) must match that principal.
- FEATURE_05 (registry-backed pool): an invalid/absent registry is never
  permissive (VERIFIER_POOL_INVALID rejects every receipt); a verifier whose
  registry status is not AUTHENTICATED rejects with the specific status
  reason (VERIFIER_UNKNOWN / VERIFIER_INACTIVE / VERIFIER_REPO_NOT_ALLOWED /
  VERIFIER_IDENTITY_UNBOUND); a bound principal equal to the PR author is a
  proven self-IV (AUTHOR_CONFLICT_BLOCKED); a receipt whose
  implementer_session_id equals its own session_id is SESSION_CONFLICT.

All FEATURE_05 checks are additive: no existing check or reason weakens.
"""
from __future__ import annotations

PASS_SHAPED_RESULTS = frozenset({"PASS", "PASS_WITH_FINDINGS"})

# Registry status -> rejection reason (FEATURE_05). DECLARED_BUT_UNBOUND
# keeps its established gate reason VERIFIER_IDENTITY_UNBOUND.
_STATUS_REASONS = {
    "VERIFIER_UNKNOWN": "VERIFIER_UNKNOWN",
    "VERIFIER_INACTIVE": "VERIFIER_INACTIVE",
    "VERIFIER_REPO_NOT_ALLOWED": "VERIFIER_REPO_NOT_ALLOWED",
    "DECLARED_BUT_UNBOUND": "VERIFIER_IDENTITY_UNBOUND",
}


def status_rejection_reason(status: str | None) -> str:
    """Map a non-AUTHENTICATED registry status to its rejection reason."""
    return _STATUS_REASONS.get(status, "VERIFIER_UNKNOWN")


def formal_iv_status(
    receipt: dict,
    pr_head: str | None,
    pr_tree: str | None,
    bindings: dict[str, str],
    declared: list[str],
    pool_present: bool,
    source_author: str | None,
    *,
    status_map: dict[str, str] | None = None,
    pool_invalid: bool = False,
    pr_author: str | None = None,
) -> tuple[bool, list[str]]:
    """Return (eligible, reasons). eligible is True only when reasons is empty."""
    reasons: list[str] = []

    if not pr_head:
        reasons.append("CANDIDATE_HEAD_UNKNOWN")
    elif receipt.get("head") != pr_head:
        reasons.append("HEAD_MISMATCH")

    if not pr_tree:
        reasons.append("CANDIDATE_TREE_UNKNOWN")
    elif receipt.get("tree") != pr_tree:
        reasons.append("TREE_MISMATCH")

    if receipt.get("formal_independence") != "PASS":
        reasons.append("FORMAL_INDEPENDENCE_NOT_PASS")

    if receipt.get("candidate_author_conflict"):
        reasons.append("AUTHOR_CONFLICT")

    if receipt.get("write_activity_count", 1) != 0:
        reasons.append("WRITE_ACTIVITY_NONZERO")

    # FEATURE_05: a bad registry rejects everything, never becomes permissive.
    if pool_invalid:
        reasons.append("VERIFIER_POOL_INVALID")

    # FEATURE_05: session distinctness. An implementer_session_id equal to
    # the verifier's own session_id proves non-distinctness on its face.
    implementer_session = receipt.get("implementer_session_id")
    if implementer_session is not None \
            and implementer_session == receipt.get("session_id"):
        reasons.append("SESSION_CONFLICT")

    verifier = receipt.get("verifier_id", "")
    if not pool_present:
        reasons.append("VERIFIER_POOL_UNDEFINED")
    elif status_map is not None:
        # Registry-backed classification: reject with the specific status
        # reason whenever the verifier is not AUTHENTICATED.
        status = status_map.get(verifier)
        if status != "AUTHENTICATED":
            reasons.append(status_rejection_reason(status))
        elif not source_author:
            reasons.append("SOURCE_IDENTITY_MISSING")
        elif bindings.get(verifier) != f"github:{source_author}":
            reasons.append("PRINCIPAL_MISMATCH")
    elif verifier in declared:
        # Bare-label declaration is NOT authentication.
        reasons.append("VERIFIER_IDENTITY_UNBOUND")
    elif verifier not in bindings:
        reasons.append("VERIFIER_NOT_APPROVED")
    else:
        if not source_author:
            reasons.append("SOURCE_IDENTITY_MISSING")
        elif bindings[verifier] != f"github:{source_author}":
            reasons.append("PRINCIPAL_MISMATCH")

    # FEATURE_05: proven self-IV. A bound principal that IS the candidate
    # author can never formally verify their own work (no_self_iv).
    if pr_author and bindings.get(verifier) == f"github:{pr_author}":
        reasons.append("AUTHOR_CONFLICT_BLOCKED")

    if receipt.get("result") not in PASS_SHAPED_RESULTS:
        reasons.append(f"RESULT_NOT_PASS_SHAPED:{receipt.get('result')}")

    return (not reasons, reasons)


def latest_eligible_receipt(
    receipts: list[dict],
    pr_head: str | None,
    pr_tree: str | None,
    bindings: dict[str, str],
    declared: list[str],
    pool_present: bool,
    *,
    status_map: dict[str, str] | None = None,
    pool_invalid: bool = False,
    pr_author: str | None = None,
) -> tuple[dict | None, dict[str, list[str]]]:
    """Pick the newest eligible receipt; return (receipt, per-receipt rejection reasons)."""
    rejected: dict[str, list[str]] = {}
    eligible: list[dict] = []
    for receipt in receipts:
        source = receipt.get("_source") or {}
        ok, why = formal_iv_status(
            receipt, pr_head, pr_tree, bindings, declared, pool_present,
            source.get("author"),
            status_map=status_map, pool_invalid=pool_invalid, pr_author=pr_author,
        )
        if ok:
            eligible.append(receipt)
        else:
            rejected[receipt["receipt_id"]] = why
    if not eligible:
        return None, rejected
    return eligible[-1], rejected
