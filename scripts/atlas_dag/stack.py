"""First-class stacked-PR DAG (FEATURE_03, D-ATLAS-DAG-FEATURE-03).

Atlas understands stacked PRs as dependency chains, not unrelated nodes:

    main -> #720 -> #723 -> #725 -> #727

Relationships are detected from live GitHub base/head refs and validated by
Git ancestry (the compare API) — never inferred from PR prose, and never
from prospective merge SHAs (a prospective merge commit is not a parent
and not a merge receipt).

Stack relation != authority: stack membership grants no ownership, no CI/
IV inheritance, and no write authority. A child is STACK_CURRENT only when
the exact live parent HEAD is an ancestor of the child HEAD; anything
unverifiable fails closed (ANCESTRY_UNKNOWN — never claimed current).

No automatic mutation: this module detects PARENT_MOVED / RESTACK_REQUIRED
but never rebases, restacks, or merges.
"""
from __future__ import annotations

ROOT = "ROOT"
STACK_CURRENT = "STACK_CURRENT"
PARENT_MOVED = "PARENT_MOVED"
RESTACK_REQUIRED = "RESTACK_REQUIRED"
PARENT_MISSING = "PARENT_MISSING_OR_UNKNOWN"
AMBIGUOUS = "AMBIGUOUS"
CYCLE_INVALID = "CYCLE_INVALID"
ANCESTRY_UNKNOWN = "ANCESTRY_UNKNOWN"

# A child with one of these states must not route as writable work.
NOT_CURRENT_STATES = frozenset({
    PARENT_MOVED,
    ANCESTRY_UNKNOWN,
    CYCLE_INVALID,
    AMBIGUOUS,
    PARENT_MISSING,
})


def _base_of(node: dict) -> str | None:
    return node.get("target_branch") or node.get("base")


def _walk_root(parent_of: dict, lane: str) -> str | None:
    """Topmost resolvable root lane, or None when the chain is broken."""
    seen: set[str] = set()
    current = lane
    while current in parent_of:
        if current in seen:
            return None  # cycle — no honest root
        seen.add(current)
        current = parent_of[current]
    return current if current else None


def build_stacks(nodes: list[dict], client, default_branch: str = "main") -> dict:
    """Stack records keyed by lane. Deterministic for equivalent inputs.

    nodes: snapshot node dicts (must carry lane/pr/head/head_branch/base).
    client: GhClient-like with is_ancestor(); ancestry failures fail closed.
    """
    ordered = sorted(nodes, key=lambda n: str(n.get("lane", "")))
    by_branch: dict[str, list[dict]] = {}
    for node in ordered:
        branch = node.get("head_branch")
        if branch:
            by_branch.setdefault(str(branch), []).append(node)

    # Pass A: identity-level parent resolution (no ancestry yet), so a
    # child's fate never depends on processing order.
    resolution: dict[str, str] = {}  # lane -> ROOT/MISSING/AMBIGUOUS/CYCLE/RESOLVED
    parent_of: dict[str, str] = {}
    parent_meta: dict[str, dict] = {}
    for node in ordered:
        lane = str(node.get("lane", "?"))
        base = _base_of(node)
        if base is None or base == default_branch:
            resolution[lane] = ROOT
            continue
        if base == node.get("head_branch"):
            resolution[lane] = CYCLE_INVALID
            continue
        candidates = by_branch.get(str(base), [])
        if not candidates:
            resolution[lane] = PARENT_MISSING
            continue
        if len(candidates) > 1:
            resolution[lane] = AMBIGUOUS
            continue
        parent = candidates[0]
        if parent.get("pr") == node.get("pr"):
            resolution[lane] = CYCLE_INVALID
            continue
        resolution[lane] = "RESOLVED"
        parent_of[lane] = str(parent.get("lane"))
        parent_meta[lane] = parent

    # Pass B: full records with ancestry validation.
    records: dict[str, dict] = {}
    for node in ordered:
        lane = str(node.get("lane", "?"))
        base = _base_of(node)
        record = {
            "lane": lane,
            "pr": node.get("pr"),
            "stack_state": ROOT,
            "stack_root": None,
            "parent_pr": None,
            "children": [],
            "depth": 0,
            "target_branch": base,
            "parent_head": None,
            "child_head": node.get("head"),
            "parent_ancestor_of_child": None,
            "restack_required": False,
            "reasons": [],
        }
        state = resolution[lane]
        if state == ROOT:
            records[lane] = record
            continue
        if state == CYCLE_INVALID:
            record["stack_state"] = CYCLE_INVALID
            record["reasons"] = ["SELF_PARENT" if base == node.get("head_branch")
                                 else "SELF_PARENT"]
            records[lane] = record
            continue
        if state == PARENT_MISSING:
            record["stack_state"] = PARENT_MISSING
            record["depth"] = None
            record["reasons"] = [
                "PARENT_BRANCH_NOT_AN_OPEN_PR:merged-closed-or-unknown"]
            records[lane] = record
            continue
        if state == AMBIGUOUS:
            record["stack_state"] = AMBIGUOUS
            record["depth"] = None
            record["reasons"] = [f"DUPLICATE_HEAD_BRANCH:{base}"]
            records[lane] = record
            continue

        parent = parent_meta[lane]
        record["parent_pr"] = parent.get("pr")
        record["parent_head"] = parent.get("head")
        parent_state = resolution[parent_of[lane]]
        if parent_state in (AMBIGUOUS, CYCLE_INVALID):
            # Parent identity is not truthfully resolvable: fail closed and
            # propagate the uncertainty (never authority).
            record["stack_state"] = AMBIGUOUS
            record["depth"] = None
            record["reasons"] = [f"PARENT_IDENTITY_UNRESOLVED:{parent_state}"]
            records[lane] = record
            continue

        ancestry = None
        if client is not None and parent.get("head") and node.get("head"):
            try:
                ancestry = client.is_ancestor(parent["head"], node["head"])
            except Exception:
                ancestry = None  # unverifiable => fail closed
        record["parent_ancestor_of_child"] = ancestry
        if ancestry is True:
            record["stack_state"] = STACK_CURRENT
        elif ancestry is False:
            record["stack_state"] = PARENT_MOVED
            record["restack_required"] = True
            record["reasons"] = ["PARENT_HEAD_NOT_IN_CHILD_ANCESTRY"]
        else:
            record["stack_state"] = ANCESTRY_UNKNOWN
            record["restack_required"] = True
            record["reasons"] = ["GIT_ANCESTRY_UNVERIFIABLE"]
        records[lane] = record

    # Cycle detection across chains (walk up; revisiting => cycle).
    for lane, record in records.items():
        if record["stack_state"] in (CYCLE_INVALID,):
            continue
        seen: list[str] = []
        current = lane
        while current in parent_of:
            if current in seen:
                for member in seen[seen.index(current):]:
                    if records[member]["stack_state"] not in (ROOT,):
                        records[member]["stack_state"] = CYCLE_INVALID
                        records[member]["restack_required"] = False
                        records[member]["reasons"] = ["CYCLE_DETECTED"]
                break
            seen.append(current)
            current = parent_of[current]

    # Depth and children (deterministic; broken chains get depth None).
    for lane, record in records.items():
        parent_lane = parent_of.get(lane)
        if parent_lane is None:
            base = record.get("target_branch")
            if base is not None and base != default_branch \
                    and record["stack_state"] != ROOT:
                record["depth"] = None  # chain broken above: depth unknown
            continue
        if record["stack_state"] == CYCLE_INVALID:
            record["depth"] = None
            continue
        broken = records[parent_lane]["depth"] is None
        depth, current, guard = 1, parent_lane, 0
        while current in parent_of and guard < len(records) + 1:
            depth += 1
            current = parent_of[current]
            guard += 1
        record["depth"] = None if broken else depth
        records[parent_lane]["children"].append(lane)

    for record in records.values():
        record["children"] = sorted(record["children"])
        record["stack_root"] = _walk_root(parent_of, record["lane"])
    return records


def chain_for(lane: str, records: dict) -> list[dict]:
    """Root-to-lane chain (deterministic), broken chains return what resolved."""
    by_pr = {r["pr"]: r["lane"] for r in records.values()}
    chain: list[dict] = []
    current: str | None = lane
    guard = 0
    while current is not None and current in records and guard < len(records) + 1:
        chain.append(records[current])
        parent_pr = records[current]["parent_pr"]
        current = by_pr.get(parent_pr)
        guard += 1
    chain.reverse()
    return chain
