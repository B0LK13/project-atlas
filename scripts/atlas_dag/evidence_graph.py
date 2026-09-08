"""Evidence dependency / invalidation graph (FEATURE_07,
EVIDENCE_DEPENDENCY_AND_INVALIDATION_GRAPH).

Extends the D-009 evidence cache into an explicit dependency model so Atlas
can machine-determine what each stored evidence artifact depends on, what
invalidates it, what becomes predecessor-only after a HEAD move, what narrow
evidence may be reused, and which explicit proof authorizes that reuse.

Core invariant: EVIDENCE_REUSE = EXPLICITLY_PROVEN_NOT_INFERRED. Candidate-wide
exact-head CI and formal IV NEVER transfer across HEAD movement. Narrow /
subsystem evidence survives a HEAD move ONLY via an explicit equivalence proof
bound to the exact transition {record.head -> live head} for the record's
covered contract — and a proof for A->B never authorizes B->C.

Reuse-proof provenance is mandatory: a proof record that does not name who
issued it, when, and which evidence it rests on is rejected
(EQUIVALENCE_PROOF_NO_PROVENANCE). Absence of detected file overlap is NOT
proof of equivalence.

Everything here is derived deterministically from the record's own fields and
caller-supplied live context. The cached store never supplies "current" truth:
`evaluate()` always takes live context from the caller (fail closed).
`evidence.py` semantics are untouched; this module layers on top.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from . import evidence as evidence_mod

# Dependency classes (controlled vocabulary).
DEP_HEAD = "HEAD"
DEP_TREE = "TREE"
DEP_PARENT_HEAD = "PARENT_HEAD"
DEP_MAIN_HEAD = "MAIN_HEAD"
DEP_PATH_SET = "PATH_SET"
DEP_SUBSYSTEM = "SUBSYSTEM"
DEP_PLATFORM = "PLATFORM"
DEP_TEST_SET = "TEST_SET"
DEP_TOOLCHAIN = "TOOLCHAIN"
DEP_VERIFIER_PRINCIPAL = "VERIFIER_PRINCIPAL"
DEP_VERIFIER_SESSION = "VERIFIER_SESSION"

# Graph states (controlled vocabulary; disjoint from evidence.classify's
# reuse classes — this module never rewrites D-009 semantics).
EXACT_CURRENT = "EXACT_CURRENT"
REUSABLE_BY_PROVEN_EQUIVALENCE = "REUSABLE_BY_PROVEN_EQUIVALENCE"
PREDECESSOR_ONLY = "PREDECESSOR_ONLY"
INVALIDATED = "INVALIDATED"
UNKNOWN = "UNKNOWN"

# Evidence classes that are candidate-wide by definition: they certify the
# whole candidate and therefore NEVER transfer across HEAD movement, no proof
# accepted. Records without an explicit evidence_class fall back to their
# scope field (CANDIDATE_WIDE is candidate-wide; SUBSYSTEM is narrow).
CANDIDATE_WIDE_CLASSES = frozenset({
    "exact_head_ci",
    "formal_iv",
    "claim_integrity",
    "freeze_validation",
    "post_merge_seal",
})

PROOF_RESULTS = evidence_mod.PROOF_RESULTS


def derive_dependencies(record: dict) -> list[dict]:
    """Explicit dependency list for one record, derived deterministically
    from the record's own fields only (never invented)."""
    deps: list[dict] = []
    head = record.get("head")
    if head:
        deps.append({"class": DEP_HEAD, "value": str(head)})
    tree = record.get("tree")
    if tree:
        deps.append({"class": DEP_TREE, "value": str(tree)})
    parent_head = record.get("parent_head")
    if parent_head:
        deps.append({"class": DEP_PARENT_HEAD, "value": str(parent_head)})
    main_head = record.get("main_head")
    if main_head:
        deps.append({"class": DEP_MAIN_HEAD, "value": str(main_head)})
    covered = sorted({str(f) for f in record.get("covered_files") or []})
    if covered:
        deps.append({"class": DEP_PATH_SET, "value": covered})
    contract = record.get("covered_contract")
    if contract:
        deps.append({"class": DEP_SUBSYSTEM, "value": str(contract)})
    for field, dep_class in (("platform", DEP_PLATFORM),
                             ("test_set", DEP_TEST_SET),
                             ("toolchain", DEP_TOOLCHAIN),
                             ("verifier_principal", DEP_VERIFIER_PRINCIPAL),
                             ("verifier_session", DEP_VERIFIER_SESSION)):
        value = record.get(field)
        if value:
            deps.append({"class": dep_class, "value": str(value)})
    return sorted(deps, key=lambda d: (d["class"], str(d["value"])))


def is_candidate_wide(record: dict) -> bool:
    """True when the artifact certifies the whole candidate (never transfers)."""
    evidence_class = str(record.get("evidence_class") or "").strip().lower()
    if evidence_class:
        return evidence_class in CANDIDATE_WIDE_CLASSES
    return str(record.get("scope", "")).upper() == "CANDIDATE_WIDE"


def _proof_provenance(proof: dict) -> dict | None:
    """Normalized provenance block, or None when any part is missing."""
    if not isinstance(proof, dict):
        return None
    provenance = proof.get("provenance")
    if not isinstance(provenance, dict):
        return None
    author = provenance.get("author") or provenance.get("principal")
    issued_at = provenance.get("issued_at_utc") or provenance.get("timestamp_utc")
    evidence_ref = provenance.get("evidence_ref") or provenance.get("evidence")
    if not author or not issued_at or not evidence_ref:
        return None
    return {"author": str(author), "issued_at_utc": str(issued_at),
            "evidence_ref": str(evidence_ref)}


def _proof_rejection_reason(proof: Any, record: dict,
                            current_head: str | None,
                            overlap: list[str]) -> str | None:
    """Return None if the proof explicitly authorizes THIS transition for THIS
    record's covered set, else a machine-readable rejection reason."""
    if proof is None:
        return "SUBSYSTEM_REUSE_REQUIRES_EQUIVALENCE_PROOF"
    if callable(proof):
        try:
            if proof(record, current_head, None):
                return None
        except Exception:
            pass  # a crashing proof proves nothing
        return "EQUIVALENCE_PROOF_REJECTED"
    if not isinstance(proof, dict):
        return "SUBSYSTEM_REUSE_REQUIRES_EQUIVALENCE_PROOF"
    if str(proof.get("result", "")).upper() not in PROOF_RESULTS:
        return "EQUIVALENCE_PROOF_NOT_PROVEN"
    if _proof_provenance(proof) is None:
        # Unprovenanced proofs are rejected outright: reuse must be
        # attributable to an author, a time, and the evidence it rests on.
        return "EQUIVALENCE_PROOF_NO_PROVENANCE"
    if proof.get("covered_contract") != record.get("covered_contract"):
        return "EQUIVALENCE_PROOF_CONTRACT_MISMATCH"
    if proof.get("old_head") != record.get("head"):
        return "EQUIVALENCE_PROOF_NOT_BOUND"
    if current_head is None or proof.get("new_head") != current_head:
        # A proof for A->B never authorizes B->C: new_head must equal the
        # live head exactly.
        return "EQUIVALENCE_PROOF_NOT_BOUND"
    declared_scope = proof.get("scope") or proof.get("covered_files")
    if not isinstance(declared_scope, list) or not all(
            isinstance(p, str) for p in declared_scope):
        return "EQUIVALENCE_PROOF_SCOPE_INVALID"
    if not set(overlap) <= {str(p) for p in declared_scope}:
        return "EQUIVALENCE_PROOF_SCOPE_INSUFFICIENT"
    return None


def _as_proof_list(proofs: Any) -> list[Any]:
    if proofs is None:
        return []
    if isinstance(proofs, list):
        return list(proofs)
    return [proofs]


def evaluate(record: dict, context: dict | None) -> dict:
    """Resolve one stored artifact against caller-supplied live truth.

    context carries the live facts: current_head, current_tree,
    current_parent_head, current_main_head, changed_files (list, or None when
    unavailable), current_platform, current_test_set, current_toolchain,
    current_verifier_principal, current_verifier_session, pr (the live lane
    this evaluation is FOR) and equivalence_proofs (explicit reuse proofs).

    The cached store never supplies "current" truth; everything is evaluated
    against the caller's context. Deterministic; reasons sorted.
    """
    ctx = context or {}
    deps = derive_dependencies(record) if isinstance(record, dict) else []
    result: dict[str, Any] = {
        "evidence_id": record.get("evidence_id") if isinstance(record, dict) else None,
        "evidence_class": (str(record.get("evidence_class")).strip().lower()
                           if isinstance(record, dict)
                           and record.get("evidence_class") else None),
        "state": UNKNOWN,
        "reasons": [],
        "dependencies": deps,
        "reuse_proof": None,
        "uncertainty": [],
    }
    malformed = evidence_mod._malformed_reasons(record)  # noqa: SLF001
    if malformed:
        result["state"] = INVALIDATED
        result["reasons"] = sorted(malformed)
        return result
    result["evidence_id"] = record["evidence_id"]
    result["evidence_class"] = str(record.get("evidence_class") or "").strip().lower() \
        or None
    result["dependencies"] = derive_dependencies(record)

    if str(record["negative_control"]).upper() == "FAIL":
        result["state"] = INVALIDATED
        result["reasons"] = ["NEGATIVE_CONTROL_FAILED"]
        return result

    context_pr = ctx.get("pr")
    if context_pr is not None and record.get("pr") != context_pr:
        # Parent/child evidence never inherits: an artifact stored for pr X
        # evaluates only against X's own context.
        result["state"] = INVALIDATED
        result["reasons"] = [f"WRONG_LANE:record_pr={record.get('pr')}"
                             f":context_pr={context_pr}"]
        return result

    current_head = ctx.get("current_head")
    current_tree = ctx.get("current_tree")
    changed_files = ctx.get("changed_files")

    head_match = bool(current_head) and record["head"] == current_head
    tree_match = bool(current_tree) and record["tree"] == current_tree

    # -- candidate-wide: exact-head certification never transfers -----------
    if is_candidate_wide(record):
        if not current_head and not current_tree:
            result["state"] = UNKNOWN
            result["reasons"] = ["CURRENT_HEAD_TREE_UNKNOWN"]
            result["uncertainty"] = ["CURRENT_HEAD_TREE_UNKNOWN"]
            return result
        env_check = _check_exact_context_deps(record, ctx)
        if env_check["state"] == INVALIDATED:
            result["state"] = INVALIDATED
            result["reasons"] = env_check["reasons"]
            return result
        if env_check["state"] == UNKNOWN:
            result["state"] = UNKNOWN
            result["uncertainty"] = env_check["uncertainty"]
            return result
        # A commit determines its tree: head equality alone certifies tree
        # equality; an absent live tree is uncertainty, not a mismatch.
        tree_current = tree_match or not current_tree
        if head_match and tree_current:
            result["state"] = EXACT_CURRENT
            result["reasons"] = ["HEAD_AND_TREE_MATCH"]
            if not current_tree:
                result["uncertainty"] = ["CURRENT_TREE_UNKNOWN"]
        else:
            reasons = []
            if not current_head or record["head"] != current_head:
                reasons.append("HEAD_MOVED" if current_head
                               else "CURRENT_HEAD_UNKNOWN")
            if current_tree and record["tree"] != current_tree:
                reasons.append("TREE_MOVED")
            result["state"] = PREDECESSOR_ONLY
            result["reasons"] = sorted(reasons)
        return result

    # -- narrow / subsystem evidence ----------------------------------------
    result.update(_evaluate_narrow(record, ctx, head_match, tree_match,
                                   changed_files))
    return result


def _check_exact_context_deps(record: dict, ctx: dict) -> dict:
    """Dependency re-verification for an exact-head artifact: environment-
    class dependencies (parent/main/platform/test-set/toolchain/verifier)
    must still hold at the live context, else the artifact is INVALIDATED."""
    for dep in derive_dependencies(record):
        dep_class = dep["class"]
        if dep_class == DEP_PARENT_HEAD:
            live = ctx.get("current_parent_head")
            if live is None:
                return {"state": UNKNOWN,
                        "reasons": [],
                        "uncertainty": ["PARENT_HEAD_UNAVAILABLE"]}
            if live != dep["value"]:
                return {"state": INVALIDATED,
                        "reasons": ["PARENT_HEAD_MOVED"],
                        "uncertainty": []}
        elif dep_class == DEP_MAIN_HEAD:
            live = ctx.get("current_main_head")
            if live is None:
                return {"state": UNKNOWN, "reasons": [],
                        "uncertainty": ["MAIN_HEAD_UNAVAILABLE"]}
            if live != dep["value"]:
                return {"state": INVALIDATED,
                        "reasons": ["MAIN_HEAD_MOVED"],
                        "uncertainty": []}
        elif dep_class == DEP_PLATFORM:
            live = ctx.get("current_platform")
            if live is not None and live != dep["value"]:
                return {"state": INVALIDATED,
                        "reasons": ["PLATFORM_MISMATCH"],
                        "uncertainty": []}
        elif dep_class == DEP_TEST_SET:
            live = ctx.get("current_test_set")
            if live is not None and live != dep["value"]:
                return {"state": INVALIDATED,
                        "reasons": ["TEST_SET_CHANGED"],
                        "uncertainty": []}
        elif dep_class == DEP_TOOLCHAIN:
            live = ctx.get("current_toolchain")
            if live is not None and live != dep["value"]:
                return {"state": INVALIDATED,
                        "reasons": ["TOOLCHAIN_CHANGED"],
                        "uncertainty": []}
        elif dep_class == DEP_VERIFIER_PRINCIPAL:
            live = ctx.get("current_verifier_principal")
            if live is not None and live != dep["value"]:
                return {"state": INVALIDATED,
                        "reasons": ["VERIFIER_PRINCIPAL_CHANGED"],
                        "uncertainty": []}
        elif dep_class == DEP_VERIFIER_SESSION:
            live = ctx.get("current_verifier_session")
            if live is not None and live != dep["value"]:
                return {"state": INVALIDATED,
                        "reasons": ["VERIFIER_SESSION_CHANGED"],
                        "uncertainty": []}
    return {"state": EXACT_CURRENT, "reasons": ["HEAD_AND_TREE_MATCH"],
            "uncertainty": []}


def _evaluate_narrow(record: dict, ctx: dict, head_match: bool,
                     tree_match: bool, changed_files: list | None) -> dict:
    """Narrow (subsystem/path-scoped) evidence: survives a HEAD move ONLY via
    an explicit equivalence proof bound to the exact transition."""
    if not ctx.get("current_head"):
        return {"state": UNKNOWN, "reasons": ["CURRENT_HEAD_TREE_UNKNOWN"],
                "reuse_proof": None, "uncertainty": ["CURRENT_HEAD_TREE_UNKNOWN"]}
    current_tree = ctx.get("current_tree")

    covered = sorted({str(f) for f in record.get("covered_files") or []})
    overlap: list[str] = []
    if changed_files is None:
        if not head_match:
            # PATH_SET dependency unavailable: never guess equivalence.
            return {"state": UNKNOWN, "reasons": ["CHANGED_FILES_UNAVAILABLE"],
                    "reuse_proof": None,
                    "uncertainty": ["CHANGED_FILES_UNAVAILABLE"]}
    else:
        changed = {str(f) for f in changed_files}
        overlap = sorted(f for f in covered if f in changed)

    env_check = _check_exact_context_deps(record, ctx)
    if env_check["state"] == INVALIDATED:
        return {"state": INVALIDATED, "reasons": env_check["reasons"],
                "reuse_proof": None, "uncertainty": []}
    if env_check["state"] == UNKNOWN:
        return {"state": UNKNOWN, "reasons": [], "reuse_proof": None,
                "uncertainty": env_check["uncertainty"]}

    if head_match:
        # A commit determines its tree: head equality certifies the tree.
        return {"state": EXACT_CURRENT, "reasons": ["HEAD_AND_TREE_MATCH"],
                "reuse_proof": None, "uncertainty": []}

    reasons = ["HEAD_MOVED"]
    if current_tree and record["tree"] != current_tree:
        reasons.append("TREE_MOVED")

    if overlap:
        reasons.append("PATHS_CHANGED")
        for proof in _as_proof_list(ctx.get("equivalence_proofs")):
            rejection = _proof_rejection_reason(proof, record,
                                                ctx.get("current_head"), overlap)
            if rejection is None:
                provenance = _proof_provenance(proof)
                return {
                    "state": REUSABLE_BY_PROVEN_EQUIVALENCE,
                    "reasons": sorted(reasons + ["EQUIVALENCE_PROOF_ACCEPTED"]),
                    "reuse_proof": {
                        "result": str(proof.get("result", "")).upper(),
                        "old_head": proof.get("old_head"),
                        "new_head": proof.get("new_head"),
                        "covered_contract": proof.get("covered_contract"),
                        "scope": sorted(str(p) for p in
                                        (proof.get("scope")
                                         or proof.get("covered_files") or [])),
                        "provenance": provenance,
                    },
                    "uncertainty": [],
                }
            reasons.append(rejection)
        return {"state": INVALIDATED, "reasons": sorted(set(reasons)),
                "reuse_proof": None, "uncertainty": []}

    # Head moved, no detected path overlap: absence of overlap is NOT proof —
    # reuse still requires an explicit bound proof. Without one the artifact
    # is history only.
    for proof in _as_proof_list(ctx.get("equivalence_proofs")):
        rejection = _proof_rejection_reason(proof, record,
                                            ctx.get("current_head"), overlap)
        if rejection is None:
            return {
                "state": REUSABLE_BY_PROVEN_EQUIVALENCE,
                "reasons": sorted(reasons + ["EQUIVALENCE_PROOF_ACCEPTED"]),
                "reuse_proof": {
                    "result": str(proof.get("result", "")).upper(),
                    "old_head": proof.get("old_head"),
                    "new_head": proof.get("new_head"),
                    "covered_contract": proof.get("covered_contract"),
                    "scope": sorted(str(p) for p in
                                    (proof.get("scope")
                                     or proof.get("covered_files") or [])),
                    "provenance": _proof_provenance(proof),
                },
                "uncertainty": [],
            }
        reasons.append(rejection)
    return {"state": PREDECESSOR_ONLY,
            "reasons": sorted(set(reasons
                                  + ["SUBSYSTEM_REUSE_REQUIRES_EQUIVALENCE_PROOF"])),
            "reuse_proof": None, "uncertainty": []}


# -- hypothetical transitions (evidence-impact) -------------------------------


def changed_files_between(repo_dir: Path | str, from_sha: str,
                          to_sha: str, runner: Any = None) -> list[str] | None:
    """Repo-relative changed paths between two commits via `git diff`
    (subprocess, explicit repo dir). None on ANY failure — fail closed, never
    guess. `runner` mirrors gh.py's test-seam style."""
    run = runner if runner is not None else subprocess.run
    try:
        proc = run(
            ["git", "diff", "--name-only", "-z", f"{from_sha}...{to_sha}"],
            cwd=str(repo_dir), capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            return None
        return sorted(p for p in (proc.stdout or "").split("\0") if p)
    except Exception:
        return None


def evidence_impact(records: list[dict], from_head: str, to_head: str,
                    changed_files: list | None,
                    context: dict | None = None) -> dict:
    """Read-only impact of a hypothetical A->B move on every artifact.

    No mutation; the store is never consulted for live truth. Each artifact is
    evaluated exactly as if the candidate head were `to_head` now. Deterministic.
    """
    ctx = dict(context or {})
    ctx["current_head"] = to_head
    ctx.setdefault("current_tree", None)
    ctx["changed_files"] = changed_files
    evaluated = []
    for record in sorted(records, key=lambda r: str(r.get("evidence_id", ""))):
        outcome = evaluate(record, ctx)
        evaluated.append({
            "evidence_id": outcome["evidence_id"],
            "evidence_class": outcome["evidence_class"],
            "state": outcome["state"],
            "reasons": outcome["reasons"],
            "reuse_proof": outcome["reuse_proof"],
            "uncertainty": outcome["uncertainty"],
        })
    return {
        "from_head": from_head,
        "to_head": to_head,
        "changed_files": sorted(str(f) for f in changed_files)
        if changed_files is not None else None,
        "changed_files_available": changed_files is not None,
        "artifacts": evaluated,
    }


def build_graph(records: list[dict], context: dict | None) -> dict:
    """Full dependency/invalidation graph for a set of artifacts against the
    caller's live context: nodes (artifacts with resolved state), dependency
    edges, reasons, reuse proofs, and unresolved uncertainty. Deterministic."""
    ctx = context or {}
    nodes = []
    for record in sorted(records, key=lambda r: str(r.get("evidence_id", ""))):
        outcome = evaluate(record, ctx)
        nodes.append({
            "evidence_id": outcome["evidence_id"],
            "evidence_class": outcome["evidence_class"],
            "pr": record.get("pr") if isinstance(record, dict) else None,
            "state": outcome["state"],
            "reasons": outcome["reasons"],
            "dependencies": outcome["dependencies"],
            "reuse_proof": outcome["reuse_proof"],
            "uncertainty": outcome["uncertainty"],
        })
    edges = []
    for node in nodes:
        for dep in node["dependencies"]:
            edges.append({"from": node["evidence_id"], "to": dep["class"],
                          "value": dep["value"]})
        # An explicit reuse proof is itself a dependency edge: the artifact's
        # reusability rests on the proof's provenance evidence.
        proof = node["reuse_proof"]
        if proof and proof.get("provenance"):
            edges.append({"from": node["evidence_id"],
                          "to": f"proof:{proof['provenance']['evidence_ref']}",
                          "value": proof["provenance"]["author"]})
    edges.sort(key=lambda e: (str(e["from"]), str(e["to"]), str(e["value"])))
    uncertainty = sorted({u for node in nodes for u in node["uncertainty"]})
    return {
        "nodes": nodes,
        "edges": edges,
        "states": {node["evidence_id"]: node["state"] for node in nodes},
        "uncertainty": uncertainty,
    }
