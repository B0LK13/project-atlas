"""AS-STUDIO-BRIDGE-001 -- the narrow seam between a Studio task-context
packet (AS-STUDIO-A2-003, #786) and a governed mission run
(AS-MISSION-VERTICAL-SLICE-001, #789).

WHY THIS MODULE IS DELIBERATELY SMALL

Studio and the mission-execution package were built on separate branches
against different assumptions, and they encode DIFFERENT things:

* A Studio task-context packet is a READ-ONLY PROJECTION. Every packet
  states `authorization = NOT_GRANTED_BY_THIS_PACKET` and asserts
  `knowledge_ne_permission` / `next_step_ne_authorization` in its own
  honesty block. `next_step.status == "SUPPORTED"` means "this action is
  the supported next one to consider", NOT "you may run it".
* `start_mission_run` enforces `context.trusted_policy`, which
  `context_packet.py` documents as "supplied by the CALLER, never derived
  from retrieved content".

So the single most important property of this bridge is a NEGATIVE one:

    A Studio packet can supply CONTEXT. It can never supply AUTHORITY.

`trusted_policy` is therefore a REQUIRED, EXPLICIT argument here. It is
never read out of the Studio packet, and `build_mission_inputs` raises
`StudioAuthorityError` if a caller tries to pass Studio-derived material
in as policy. A subprocess adapter does not inherit Studio's permissions
just because Studio rendered a green row.

WHAT THE BRIDGE DOES CHECK

Studio state is used as a PRECONDITION (a reason to refuse), never as a
grant:

* `NO_SUPPORTED_ACTION`            -> refuse (nothing to carry).
* `freshness.state != "LIVE"`      -> refuse unless `allow_stale=True`,
                                      mirroring `ContextStaleError`.
* agent identity mismatch          -> refuse; the bridge never silently
                                      substitutes an actor.
* a WRITE-class next step          -> refuse unless the caller's own
                                      policy explicitly permits that class.

Everything the bridge passes downstream is data: objective text, keywords
for the context compiler, and evidence links.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA_CONST = "ATLAS_STUDIO_TASK_CONTEXT_V1"

#: Studio action classes that mutate something outside the workspace.
WRITE_CLASSES = frozenset({"WRITE", "HUMAN_GATE"})

#: Keys a caller may never source from a Studio packet into trusted_policy.
_STUDIO_ONLY_KEYS = frozenset({
    "authorization", "next_step", "lane_state", "attention", "honesty",
})


class StudioBridgeError(Exception):
    """Base class for every refusal this bridge raises."""


class StudioAuthorityError(StudioBridgeError):
    """A caller tried to derive AUTHORITY from a Studio packet.

    Studio packets are read-only projections that explicitly disclaim
    granting permission; turning one into `trusted_policy` would silently
    convert a rendered row into an execution grant.
    """


class StudioPreconditionError(StudioBridgeError):
    """Studio's own state says this run must not be carried forward."""


@dataclass(frozen=True)
class MissionInputs:
    """The data-only inputs a Studio packet contributes to a mission run."""

    mission_id: str
    objective: str
    keywords: list[str]
    evidence_links: list[str]
    lane: str
    agent_id: str
    action_type: str
    action_class: str
    lane_head: str | None
    studio_fingerprint: str | None
    freshness_state: str


def _require_mapping(packet: Any) -> dict[str, Any]:
    if not isinstance(packet, dict):
        raise StudioPreconditionError(
            f"task-context packet must be a JSON object, got {type(packet).__name__}"
        )
    schema = packet.get("schema")
    if schema not in (None, SCHEMA_CONST):
        raise StudioPreconditionError(f"unexpected packet schema: {schema!r}")
    return packet


def assert_packet_grants_nothing(packet: dict[str, Any]) -> None:
    """Fail closed unless the packet still disclaims authorization.

    This is a real check, not decoration: if a future Studio revision ever
    stopped emitting `NOT_GRANTED_BY_THIS_PACKET`, this bridge must stop
    working rather than quietly start treating projections as grants.
    """
    next_step = packet.get("next_step") or {}
    auth = next_step.get("authorization")
    if auth != "NOT_GRANTED_BY_THIS_PACKET":
        raise StudioAuthorityError(
            f"task-context packet no longer disclaims authorization "
            f"(next_step.authorization={auth!r}); refusing to treat it as a grant"
        )


def validate_trusted_policy(trusted_policy: dict[str, Any]) -> dict[str, Any]:
    """Return the caller's policy, or refuse if it looks Studio-derived."""
    if not isinstance(trusted_policy, dict):
        raise StudioAuthorityError("trusted_policy must be an explicit dict")
    leaked = _STUDIO_ONLY_KEYS & set(trusted_policy)
    if leaked:
        raise StudioAuthorityError(
            f"trusted_policy contains Studio-derived keys {sorted(leaked)}; "
            f"authority must come from the caller, never from the packet"
        )
    return dict(trusted_policy)


def build_mission_inputs(
    packet: dict[str, Any],
    *,
    expected_agent_id: str,
    allow_stale: bool = False,
    allow_write_class: bool = False,
) -> MissionInputs:
    """Extract the data-only mission inputs a Studio packet contributes.

    Raises `StudioPreconditionError` when Studio's own state says the run
    must not proceed, and `StudioAuthorityError` if the packet has stopped
    disclaiming authorization. Never returns policy.
    """
    packet = _require_mapping(packet)
    assert_packet_grants_nothing(packet)

    agent = packet.get("agent")
    agent_id = agent.get("agent_id") if isinstance(agent, dict) else agent
    if agent_id != expected_agent_id:
        raise StudioPreconditionError(
            f"packet actor {agent_id!r} != expected {expected_agent_id!r}; "
            f"the bridge never substitutes an actor identity"
        )

    next_step = packet.get("next_step") or {}
    status = next_step.get("status")
    if status != "SUPPORTED":
        reasons = next_step.get("reasons") or []
        raise StudioPreconditionError(
            f"no supported next action (status={status!r}, reasons={list(reasons)})"
        )

    action = next_step.get("action") or {}
    action_class = str(action.get("action_class") or "")
    action_type = str(action.get("action_type") or "")
    if action_class in WRITE_CLASSES and not allow_write_class:
        raise StudioPreconditionError(
            f"next action {action_type!r} is class {action_class!r}; the caller's "
            f"policy must explicitly opt in via allow_write_class"
        )

    freshness = packet.get("freshness") or {}
    fresh_state = str(freshness.get("state") or "UNKNOWN")
    if fresh_state != "LIVE" and not allow_stale:
        raise StudioPreconditionError(
            f"task context is {fresh_state}, not LIVE; refusing (pass allow_stale=True "
            f"to proceed on a packet the caller has independently judged usable)"
        )

    lane = str(packet.get("lane") or "")
    continuation = packet.get("continuation") or {}
    fps = continuation.get("fingerprints") or {}

    knowledge = packet.get("knowledge") or {}
    lenses = knowledge.get("lenses") or {}
    evidence_links = sorted(
        str(v.get("provenance", {}).get("generator"))
        for v in lenses.values()
        if isinstance(v, dict) and isinstance(v.get("provenance"), dict)
    )

    raw_words = lane.replace("/", " ").split() + action_type.lower().split("_")
    keywords = sorted({w for w in raw_words if w})

    return MissionInputs(
        mission_id=f"studio:{lane}:{action_type}" if lane else f"studio:{action_type}",
        objective=f"{action_type} on {lane} (carried from Studio task-context)",
        keywords=keywords,
        evidence_links=evidence_links,
        lane=lane,
        agent_id=str(agent_id),
        action_type=action_type,
        action_class=action_class,
        lane_head=fps.get("lane_head"),
        studio_fingerprint=continuation.get("fingerprint"),
        freshness_state=fresh_state,
    )
