"""AT3-052 — Isolated ADV binding.

Binds an adversarial result to one exact HEAD/TREE pair.
ADV != MERGE. ADV != SECURITY CERTIFICATION. Target movement fails closed.
Never writes Truth Core. MERGE_AUTHORIZATION remains NOT_GRANTED.
"""

from __future__ import annotations

import re
from typing import Any, Final

from project_atlas.atlas3.contracts import TRUTH_BOUNDARY, Atlas3Error, honesty_block

PACKAGE_ID: Final[str] = "AT3-052"
GENERATOR_ID: Final[str] = "atlas3-adv-bind-052"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_FORBIDDEN_ACTORS = frozenset({"implementer", "self", "same-agent", "model"})


def _sha(value: str, *, field: str) -> str:
    digest = value.strip().lower()
    if not _SHA_RE.fullmatch(digest):
        raise Atlas3Error("ADV_OBJECT_INVALID", f"{field} must be a 40-char lowercase hex SHA")
    return digest


def bind_adversarial_result(
    *,
    candidate_head: str,
    candidate_tree: str,
    observed_head: str,
    observed_tree: str,
    adv_result: str,
    adv_id: str,
    package_id: str,
) -> dict[str, Any]:
    """Bind ADV to an exact object. Never grants merge or security certification."""
    pkg = package_id.strip()
    if not pkg:
        raise Atlas3Error("PACKAGE_REQUIRED", "package_id is required")
    actor = adv_id.strip()
    if not actor:
        raise Atlas3Error("ADV_ID_REQUIRED", "adv_id is required")
    if actor.lower() in _FORBIDDEN_ACTORS:
        raise Atlas3Error("IMPLEMENTER_IS_ADV", "IMPLEMENTER != ADV")
    cand_head = _sha(candidate_head, field="candidate_head")
    cand_tree = _sha(candidate_tree, field="candidate_tree")
    obs_head = _sha(observed_head, field="observed_head")
    obs_tree = _sha(observed_tree, field="observed_tree")
    if cand_head != obs_head or cand_tree != obs_tree:
        raise Atlas3Error("TARGET_MOVED", "ADV binding refused because HEAD/TREE moved")
    result = adv_result.strip().upper()
    if result not in {"PASS", "FAIL"}:
        raise Atlas3Error("ADV_RESULT_INVALID", "adv_result must be PASS or FAIL")
    if result != "PASS":
        raise Atlas3Error("ADV_FAILED", "adversarial verification did not pass")
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "bound_package": pkg,
        "candidate_head": cand_head,
        "candidate_tree": cand_tree,
        "observed_head": obs_head,
        "observed_tree": obs_tree,
        "adv_result": result,
        "adv_id": actor,
        "bound": True,
        "head_match": True,
        "tree_match": True,
        "certified_for_merge": False,
        "security_certification": False,
        "external_security_revalidation_required": True,
        "merge_authorization": "NOT_GRANTED",
        "implementer_is_adv": False,
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
