"""Agent & capability registry (FEATURE_01, ATLAS_AGENT_REGISTRY_V1).

Machine-readable answer to: which agent is this, what may it do, on which
platform/surface, and what is it explicitly prohibited from doing?

Trust model — capability is NOT authority (D-ATLAS-DAG-FEATURE-01):

* A capability never grants lane ownership; ownership is repository truth
  (#719 OWNER_CLAIMED events / the model's lane mutex), and a conflicting
  active owner always wins over any registry declaration.
* A capability never bypasses a certified-surface freeze; freeze state is
  repository truth carried in the request context.
* A capability never grants merge authority: no registry entry can produce
  MERGE authority, and the AUTO_MERGE prohibition exists to make the denial
  explicit per profile.
* A verification_class of INDEPENDENT_VERIFIER describes a role only. The
  registry does NOT bind verifier identities to trusted principals; formal
  IV remains verifier-gated (ATLAS_VERIFIER_POOL_V1 principal binding is a
  later feature). `evaluate` therefore NEVER returns allow for receipt
  publication or formal-IV satisfaction.
* Inactive profiles describe dormant logical roles, not running sessions:
  an inactive agent has no current authority at all.
* Unknown agents, missing registries, duplicate IDs, unknown enum values,
  and conflicting capability/prohibition declarations all fail closed —
  never a permissive default.

The registry informs routing (FEATURE_02); it does not change frontier
routing policy and it cannot convert an OWNER/IV/POLICY-gated node into
writable work.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .events import validator_for

REGISTRY_SCHEMA = "atlas_agent_registry_v1.schema.json"
REGISTRY_SCHEMA_CONST = "ATLAS_AGENT_REGISTRY_V1"

# Request actions (controlled vocabulary; anything else is rejected).
ACTION_READ = "read"
ACTION_WRITE = "write"
ACTION_POST_EVENT = "post_event"
ACTION_POST_RECEIPT = "post_receipt"
ACTION_CLAIM_LANE = "claim_lane"
ACTION_MERGE = "merge"
ACTION_SATISFY_FORMAL_IV = "satisfy_formal_iv"
ACTION_RUN_ON_PLATFORM = "run_on_platform"
KNOWN_ACTIONS = frozenset({
    ACTION_READ,
    ACTION_WRITE,
    ACTION_POST_EVENT,
    ACTION_POST_RECEIPT,
    ACTION_CLAIM_LANE,
    ACTION_MERGE,
    ACTION_SATISFY_FORMAL_IV,
    ACTION_RUN_ON_PLATFORM,
})

# Capabilities required per action (receipt/IV/merge have none: not grantable).
_ACTION_CAPABILITIES = {
    ACTION_READ: frozenset({"READ_REPO", "READ_GITHUB"}),
    ACTION_WRITE: frozenset({"WRITE_CODE", "WRITE_TESTS", "WRITE_DOCS"}),
    ACTION_POST_EVENT: frozenset({"POST_EVENTS"}),
    ACTION_CLAIM_LANE: frozenset({"CLAIM_OWNERSHIP"}),
    ACTION_RUN_ON_PLATFORM: frozenset(),
}


@dataclass
class AgentRequest:
    """One authorization question against repository-truth context.

    lane_owner / lane_frozen are NOT registry declarations: they are the
    current live context (e.g. from the DAG snapshot / #719 ownership).
    The registry can only ever be more restrictive than that context.
    """

    action: str
    platform: str | None = None
    scope: str | None = None  # repo-relative path (write) or github surface
    lane_owner: str | None = None  # active owner agent_id for the lane, if any
    lane_frozen: bool = False
    event_type: str | None = None


@dataclass
class RegistryResult:
    registry: dict | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.registry is not None and not self.errors


@dataclass
class ProfileResult:
    profile: dict | None = None
    status: str = "UNKNOWN_AGENT"  # REGISTERED / UNKNOWN_AGENT / PROFILE_INVALID
    errors: list[str] = field(default_factory=list)


def default_registry_path() -> Path:
    return Path(__file__).resolve().parents[2] / "registry" / "agents.json"


def _semantic_errors(registry: Any) -> list[str]:
    """Registry-wide invariants the JSON schema cannot express."""
    errors: list[str] = []
    if not isinstance(registry, dict):
        return ["REGISTRY_NOT_AN_OBJECT"]
    agents = registry.get("agents")
    if not isinstance(agents, list):
        return ["AGENTS_NOT_A_LIST"]
    seen: set[str] = set()
    for pos, profile in enumerate(agents):
        if not isinstance(profile, dict):
            errors.append(f"AGENT_NOT_AN_OBJECT:{pos}")
            continue
        agent_id = profile.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            errors.append(f"AGENT_ID_MISSING:{pos}")
            continue
        if agent_id in seen:
            errors.append(f"DUPLICATE_AGENT_ID:{agent_id}")
        seen.add(agent_id)
        capabilities = {str(c) for c in profile.get("capabilities", [])}
        prohibitions = {str(p) for p in profile.get("prohibitions", [])}
        conflict = capabilities & prohibitions
        if conflict:
            errors.append(f"CONFLICTING_DECLARATION:{agent_id}:{sorted(conflict)}")
        # Receipts are not an event permission: IV receipts travel under
        # ATLAS_IV_RECEIPT_V1 and require trusted-principal authentication.
        if "ATLAS_IV_RECEIPT_V1" in {str(e) for e in profile.get("event_permissions", [])}:
            errors.append(f"RECEIPT_NOT_AN_EVENT_PERMISSION:{agent_id}")
        # Only a verifier-role profile may carry verification_class
        # INDEPENDENT_VERIFIER, and it still grants nothing by itself.
        if profile.get("verification_class") == "INDEPENDENT_VERIFIER" \
                and not str(profile.get("role", "")).lower().find("verifier") >= 0:
            errors.append(f"VERIFIER_CLASS_REQUIRES_VERIFIER_ROLE:{agent_id}")
    return sorted(errors)


def load_registry(path: Path | str | None = None) -> RegistryResult:
    """Load + validate the registry. Missing/malformed => fail closed."""
    reg_path = Path(path) if path is not None else default_registry_path()
    if not reg_path.exists():
        return RegistryResult(errors=[f"REGISTRY_MISSING:{reg_path}"])
    try:
        registry = json.loads(reg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return RegistryResult(errors=[f"REGISTRY_UNREADABLE:{exc}"])
    validator = validator_for(REGISTRY_SCHEMA)
    errors = sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(registry)
    )
    errors.extend(_semantic_errors(registry))
    if errors:
        return RegistryResult(errors=errors)
    return RegistryResult(registry=registry)


def resolve_agent(result: RegistryResult, agent_id: str) -> ProfileResult:
    """Resolve one profile. Unknown/invalid/missing => fail closed."""
    if not result.valid:
        return ProfileResult(status="REGISTRY_INVALID", errors=list(result.errors))
    agents = result.registry["agents"] if result.registry else []
    match = next((a for a in agents if a.get("agent_id") == agent_id), None)
    if match is None:
        return ProfileResult(status="UNKNOWN_AGENT")
    return ProfileResult(profile=match, status="REGISTERED")


def _scope_allowed(profile: dict, scope: str | None) -> bool:
    """A write scope covers an action scope exactly or as a path prefix."""
    if scope is None:
        return False
    scopes = [str(s) for s in profile.get("write_scopes", [])]
    for declared in scopes:
        if declared == scope:
            return True
        if declared.startswith("path:") and scope.startswith("path:"):
            prefix = declared[len("path:"):].rstrip("/")
            target = scope[len("path:"):]
            if target == prefix or target.startswith(prefix + "/"):
                return True
    return False


def scope_covers(profile: dict, scope: str) -> bool:
    """Public wrapper: does the profile's write_scopes cover this scope?"""
    return _scope_allowed(profile, scope)


def evaluate(profile: dict | None, request: AgentRequest) -> tuple[bool, list[str]]:
    """Fail-closed authorization: (allowed, sorted reasons).

    Deny-by-default: every path below ends in a deny unless an explicit
    capability + scope + platform + repository-truth context all agree.
    """
    if profile is None:
        return False, sorted({"UNKNOWN_AGENT", "NO_INFERRED_WRITE_AUTHORITY"})

    agent_id = str(profile.get("agent_id", "?"))

    if request.action not in KNOWN_ACTIONS:
        return False, sorted({f"UNKNOWN_ACTION:{request.action}"})

    # Authority that the registry can never grant, to any profile, ever —
    # checked before session state so the reason is always informative.
    if request.action == ACTION_MERGE:
        return False, sorted({"MERGE_AUTHORITY_NOT_GRANTABLE_BY_REGISTRY"})
    if request.action == ACTION_SATISFY_FORMAL_IV:
        return False, sorted({"FORMAL_IV_NOT_GRANTABLE_BY_REGISTRY",
                              "VERIFIER_PRINCIPAL_AUTHENTICATION_NOT_IMPLEMENTED"})
    if request.action == ACTION_POST_RECEIPT:
        return False, sorted({"RECEIPT_REQUIRES_TRUSTED_PRINCIPAL",
                              "VERIFIER_PRINCIPAL_AUTHENTICATION_NOT_IMPLEMENTED"})

    if not profile.get("active", False):
        return False, sorted({"AGENT_INACTIVE", "NO_CURRENT_SESSION"})

    capabilities = {str(c) for c in profile.get("capabilities", [])}
    prohibitions = {str(p) for p in profile.get("prohibitions", [])}

    # Repository-truth context always wins over registry declarations.
    if request.lane_frozen and "BYPASS_FREEZE" not in prohibitions:
        return False, sorted({"LANE_FROZEN_BY_REPOSITORY_TRUTH"})
    if request.lane_frozen:
        return False, sorted({"LANE_FROZEN_BY_REPOSITORY_TRUTH",
                              "REGISTRY_CANNOT_OVERRIDE_FREEZE"})
    if request.lane_owner is not None and request.lane_owner != agent_id:
        return False, sorted({"OWNERSHIP_MUTEX_HELD_BY_OTHER"})

    # Platform boundary: a linux-only profile can never imply windows-native
    # authority (and vice versa); "any" is the only wildcard.
    if request.platform is not None:
        platforms = {str(p) for p in profile.get("platforms", [])}
        if "any" not in platforms and request.platform not in platforms:
            return False, sorted({f"PLATFORM_NOT_SUPPORTED:{request.platform}"})

    # Action-specific capability gates.
    if request.action == ACTION_RUN_ON_PLATFORM:
        return True, ["PLATFORM_DECLARED"]
    required = _ACTION_CAPABILITIES.get(request.action, frozenset())
    if required and not (capabilities & required):
        return False, sorted({f"CAPABILITY_MISSING:{sorted(required)}",
                              f"FOR_ACTION:{request.action}"})
    if request.action == ACTION_POST_EVENT:
        allowed_events = {str(e) for e in profile.get("event_permissions", [])}
        if request.event_type is None or request.event_type not in allowed_events:
            return False, sorted({f"EVENT_TYPE_NOT_PERMITTED:{request.event_type}"})
        return True, ["EVENT_PERMITTED"]
    if request.action == ACTION_CLAIM_LANE:
        if request.lane_owner is not None:
            return False, sorted({"OWNERSHIP_MUTEX_HELD_BY_OTHER"})
        return True, ["LANE_UNOWNED"]
    if request.action == ACTION_WRITE:
        if not _scope_allowed(profile, request.scope):
            return False, sorted({f"WRITE_SCOPE_NOT_COVERED:{request.scope}"})
        return True, ["WRITE_SCOPE_COVERED"]
    return True, ["CAPABILITY_PRESENT"]
