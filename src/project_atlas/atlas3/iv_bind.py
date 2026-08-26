"""AT3-051 — Isolated independent-verification binding.

Binds an IV result to one exact HEAD/TREE pair.
IMPLEMENTER != VERIFIER. IV != MERGE. Target movement fails closed.
Never writes Truth Core. MERGE_AUTHORIZATION remains NOT_GRANTED.
"""

from __future__ import annotations

import re
from typing import Any, Final

from project_atlas.atlas3.contracts import TRUTH_BOUNDARY, Atlas3Error, honesty_block

PACKAGE_ID: Final[str] = "AT3-051"
GENERATOR_ID: Final[str] = "atlas3-iv-bind-051"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_FORBIDDEN_VERIFIERS = frozenset({"implementer", "self", "same-agent", "model"})


def _sha(value: str, *, field: str) -> str:
    digest = value.strip().lower()
    if not _SHA_RE.fullmatch(digest):
        raise Atlas3Error("IV_OBJECT_INVALID", f"{field} must be a 40-char lowercase hex SHA")
    return digest


def bind_independent_verification(
    *,
    candidate_head: str,
    candidate_tree: str,
    observed_head: str,
    observed_tree: str,
    iv_result: str,
    verifier_id: str,
    package_id: str,
) -> dict[str, Any]:
    """Bind IV to an exact object. Never grants merge."""
    pkg = package_id.strip()
    if not pkg:
        raise Atlas3Error("PACKAGE_REQUIRED", "package_id is required")
    verifier = verifier_id.strip()
    if not verifier:
        raise Atlas3Error("VERIFIER_REQUIRED", "verifier_id is required")
    if verifier.lower() in _FORBIDDEN_VERIFIERS:
        raise Atlas3Error("IMPLEMENTER_IS_VERIFIER", "IMPLEMENTER != VERIFIER")
    cand_head = _sha(candidate_head, field="candidate_head")
    cand_tree = _sha(candidate_tree, field="candidate_tree")
    obs_head = _sha(observed_head, field="observed_head")
    obs_tree = _sha(observed_tree, field="observed_tree")
    if cand_head != obs_head or cand_tree != obs_tree:
        raise Atlas3Error("TARGET_MOVED", "IV binding refused because HEAD/TREE moved")
    result = iv_result.strip().upper()
    if result not in {"PASS", "FAIL"}:
        raise Atlas3Error("IV_RESULT_INVALID", "iv_result must be PASS or FAIL")
    if result != "PASS":
        raise Atlas3Error("IV_FAILED", "independent verification did not pass")
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "bound_package": pkg,
        "candidate_head": cand_head,
        "candidate_tree": cand_tree,
        "observed_head": obs_head,
        "observed_tree": obs_tree,
        "iv_result": result,
        "verifier_id": verifier,
        "bound": True,
        "head_match": True,
        "tree_match": True,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "implementer_is_verifier": False,
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
