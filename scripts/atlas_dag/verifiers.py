"""Verifier trust pool (FEATURE_05, ATLAS_VERIFIER_POOL_V1).

Canonical source of formal-IV authentication: the tracked registry file
`registry/verifiers.json`. Core trust principle:

    VERIFIER_ROLE != AUTHENTICATED_FORMAL_VERIFIER

A bare verifier label (IV-A / IV-B) without a principal binding in the
registry is DECLARED_BUT_UNBOUND and can NEVER satisfy formal IV. The
committed registry deliberately declares IV-A and IV-B with
`principal: null`; real bindings arrive only via future owner commits to
the registry file (the owner-approved binding location). No principal is
ever invented or inferred.

Pool resolution for the DAG snapshot (`resolve_pool`):

- A valid registry FILE is canonical. Its entries are authenticated only
  when active AND principal-bound AND repo-allowed.
- `events.parse_verifier_pool` (the #719 issue-body block) is kept for
  backward compatibility ONLY as a fallback when the registry file is
  ABSENT (pre-registry checkouts). The fallback is never consulted when
  the registry file is present-but-invalid (fail closed), and it can
  never add bindings that the file-based pool would not also produce:
  the same authentication_status / pool_views logic classifies every
  entry, so bare-string declarations stay DECLARED_BUT_UNBOUND in both
  sources.
- Registry membership grants NO merge or write authority. The pool is
  consulted exclusively for formal-IV receipt authentication; the Merge
  Guardian and the router never read it for write/merge decisions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import events as events_mod
from .events import validator_for

POOL_SCHEMA = "atlas_verifier_pool_v1.schema.json"
POOL_SCHEMA_CONST = "ATLAS_VERIFIER_POOL_V1"

# Verifier authentication statuses (controlled vocabulary).
AUTHENTICATED = "AUTHENTICATED"
DECLARED_BUT_UNBOUND = "DECLARED_BUT_UNBOUND"
VERIFIER_UNKNOWN = "VERIFIER_UNKNOWN"
VERIFIER_INACTIVE = "VERIFIER_INACTIVE"
VERIFIER_REPO_NOT_ALLOWED = "VERIFIER_REPO_NOT_ALLOWED"

# Failure classes at load time (distinct, deterministic, sorted).
POOL_MISSING = "POOL_MISSING"
POOL_UNREADABLE = "POOL_UNREADABLE"
POOL_SCHEMA_VIOLATION = "POOL_SCHEMA_VIOLATION"
POOL_DUPLICATE_VERIFIER_ID = "POOL_DUPLICATE_VERIFIER_ID"


@dataclass
class PoolResult:
    """Loaded pool or structured failure. Missing/malformed => fail closed."""

    pool: dict | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.pool is not None and not self.errors


@dataclass
class PoolResolution:
    """Pool as consumed by the snapshot / receipt gate.

    bindings: verifier_id -> trusted principal, ONLY for AUTHENTICATED
    entries. declared: sorted bare/unbound/inactive ids — never satisfies
    IV. present: a usable pool source exists. source: "registry",
    "issue_body" (legacy fallback), or "none". pool_invalid: the registry
    file was present but bad (or resolution required it and it was
    missing with fallback disallowed) — fail closed, never permissive.
    """

    bindings: dict[str, str]
    declared: list[str]
    present: bool
    source: str
    status_map: dict[str, str] | None = None  # registry source only; None => legacy path
    pool_invalid: bool = False
    errors: list[str] = field(default_factory=list)


def default_pool_path() -> Path:
    return Path(__file__).resolve().parents[2] / "registry" / "verifiers.json"


def _semantic_errors(pool: Any) -> list[str]:
    """Pool-wide invariants the JSON schema cannot express."""
    errors: list[str] = []
    if not isinstance(pool, dict):
        return ["POOL_NOT_AN_OBJECT"]
    verifiers = pool.get("verifiers")
    if not isinstance(verifiers, list):
        return ["VERIFIERS_NOT_A_LIST"]
    seen: set[str] = set()
    for pos, entry in enumerate(verifiers):
        if not isinstance(entry, dict):
            continue  # schema violation, already reported
        verifier_id = entry.get("verifier_id")
        if not isinstance(verifier_id, str) or not verifier_id:
            continue  # schema violation, already reported
        if verifier_id in seen:
            errors.append(f"{POOL_DUPLICATE_VERIFIER_ID}:{verifier_id}")
        seen.add(verifier_id)
    return sorted(errors)


def load_pool(path: Path | str | None = None) -> PoolResult:
    """Load + schema-validate the registry file.

    Every failure class is distinct: POOL_MISSING (absent file),
    POOL_UNREADABLE (I/O or invalid JSON), POOL_SCHEMA_VIOLATION (schema
    rejection, with jsonpath detail), POOL_DUPLICATE_VERIFIER_ID
    (semantic rejection). All fail closed.
    """
    pool_path = Path(path) if path is not None else default_pool_path()
    if not pool_path.exists():
        return PoolResult(errors=[f"{POOL_MISSING}:{pool_path}"])
    try:
        pool = json.loads(pool_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return PoolResult(errors=[f"{POOL_UNREADABLE}:{pool_path}: {exc}"])
    validator = validator_for(POOL_SCHEMA)
    errors = sorted(
        f"{POOL_SCHEMA_VIOLATION}:{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(pool)
    )
    errors.extend(f"{POOL_DUPLICATE_VERIFIER_ID}:{e}"
                  for e in _semantic_errors(pool))
    if errors:
        return PoolResult(errors=errors)
    return PoolResult(pool=pool)


def authentication_status(entry: dict | None, repo: str | None) -> str:
    """Classify one pool entry against a repository.

    Precedence: unknown -> inactive -> unbound -> repo-not-allowed ->
    authenticated. A verifier bound for another repository only is not
    authenticated here.
    """
    if entry is None:
        return VERIFIER_UNKNOWN
    if not entry.get("active", False):
        return VERIFIER_INACTIVE
    principal = entry.get("principal")
    if not isinstance(principal, str) or not principal.strip():
        return DECLARED_BUT_UNBOUND
    repos = [str(r) for r in entry.get("allowed_repositories", [])]
    if repo is not None and repo not in repos:
        return VERIFIER_REPO_NOT_ALLOWED
    return AUTHENTICATED


def pool_views(
    pool: dict,
    repo: str | None,
) -> tuple[dict[str, str], list[str], dict[str, str]]:
    """Reduce a valid pool to (bindings, declared, status_map).

    bindings maps verifier_id -> principal ONLY for AUTHENTICATED
    entries. declared is the sorted set of every other known id (bare,
    unbound, inactive, repo-not-allowed): declared roles never satisfy
    formal IV. status_map carries the full status per id for rich
    rejection reasons.
    """
    bindings: dict[str, str] = {}
    declared: list[str] = []
    status_map: dict[str, str] = {}
    for entry in pool.get("verifiers", []):
        verifier_id = str(entry.get("verifier_id", ""))
        status = authentication_status(entry, repo)
        status_map[verifier_id] = status
        if status == AUTHENTICATED:
            bindings[verifier_id] = str(entry["principal"]).strip()
        else:
            declared.append(verifier_id)
    return bindings, sorted(set(declared)), status_map


def empty_resolution(pool_invalid: bool, errors: list[str]) -> PoolResolution:
    return PoolResolution(
        bindings={}, declared=[], present=False, source="none",
        status_map={}, pool_invalid=pool_invalid, errors=sorted(errors),
    )


def resolve_pool(
    issue_body: str | None = None,
    path: Path | str | None = None,
    repo: str | None = None,
    *,
    allow_issue_fallback: bool = True,
) -> PoolResolution:
    """Resolve the effective verifier pool for one snapshot build.

    The registry file is canonical. Only when it is ABSENT (and fallback
    is allowed) is the legacy #719 issue-body block parsed — the fallback
    is classified by the same status logic, so it can never add bindings
    the file-based pool would reject. A present-but-invalid registry is
    fail-closed (pool_invalid=True, no fallback, nothing eligible).
    """
    result = load_pool(path)
    if result.valid and result.pool is not None:
        bindings, declared, status_map = pool_views(result.pool, repo)
        return PoolResolution(
            bindings=bindings, declared=declared, present=True,
            source="registry", status_map=status_map,
        )
    if any(e.startswith(POOL_MISSING) for e in result.errors) \
            and allow_issue_fallback:
        fb_bindings, fb_declared, fb_present = events_mod.parse_verifier_pool(issue_body)
        return PoolResolution(
            bindings=fb_bindings, declared=fb_declared, present=fb_present,
            source="issue_body" if fb_present else "none",
        )
    return empty_resolution(pool_invalid=True, errors=result.errors)


def pool_summary(resolution: PoolResolution, total: int | None = None) -> dict:
    """Deterministic counts for snapshot/CLI summaries."""
    statuses = list(resolution.status_map.values()) if resolution.status_map else []
    summary = {
        "source": resolution.source,
        "present": resolution.present,
        "invalid": resolution.pool_invalid,
        "total": total if total is not None else len(statuses),
        "authenticated": statuses.count(AUTHENTICATED),
        "unbound": statuses.count(DECLARED_BUT_UNBOUND),
        "inactive": statuses.count(VERIFIER_INACTIVE),
        "repo_not_allowed": statuses.count(VERIFIER_REPO_NOT_ALLOWED),
        "errors": sorted(resolution.errors),
    }
    return summary
