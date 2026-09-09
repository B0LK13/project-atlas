"""AS-OBSIDIAN-CAPTURE-001 F19 -- attribution for protected writes.

F18 answers *whether* a protected write altered operator bytes. It cannot
answer *who did it*: the recorded stack names the innermost frame inside
``src/project_atlas``, which identifies the plumbing a write travelled
through, not the execution responsible for it.

This module answers the responsibility question, and it deliberately does not
invent a new identity system to do it. Atlas already has one.
``AgentLease`` (``orchestration/autonomy/models.py``) carries every field the
question needs:

===========================  ==================================================
execution identity           ``agent_id``, ``lease_id``
authority context            ``capabilities``, ``authorized_paths``,
                             ``forbidden_paths``, ``active``
which exact state            ``base_pin`` (40-char git SHA)
===========================  ==================================================

The lease record was already well formed. What did not exist was any
connection between it and a write. That connection -- and only that -- is what
this module adds.

Binding primitive
-----------------
A ``ContextVar``. It follows the execution rather than the call site, so it
survives helpers, wrappers, aliases and ``await``; a write ten frames below
``bind()`` is still attributed to the lease that was active. It does **not**
cross a process boundary, which is correct rather than unfortunate: a
subprocess carries no trusted identity, so claiming attribution across that
boundary would be laundering an unknown into a known.

What this is and is not
-----------------------
This binding is trustworthy against accident, refactoring and ordinary
mistakes. It is **not** a security boundary against hostile in-process code:
anything running in this interpreter can reach ``_MINTED`` and mint itself a
token, exactly as it can monkeypatch the boundary that observes it. Nothing
inside a process can defend against arbitrary code inside that same process.
That limitation is pinned by a test rather than left to be discovered.
"""

from __future__ import annotations

import contextvars
import os
import pathlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "Attribution",
    "AttributionLedger",
    "ProtectedWrite",
    "bind",
]


class Attribution(StrEnum):
    """The classification vocabulary, used without widening any state.

    Each member states exactly what is known. The states are not ranked and
    one is never substituted for a neighbour to make a report look better:
    ``UNKNOWN`` in particular is a real answer, not a placeholder.
    """

    #: A trusted lease was active and the path lies inside its authorized
    #: scope. This is the only state that claims the write was *permitted*.
    GOVERNED_AND_ATTRIBUTED = "GOVERNED_AND_ATTRIBUTED"

    #: A trusted lease was active and the path lies outside it (or inside its
    #: forbidden set). The responsible execution is known *and* it was out of
    #: scope -- the most actionable finding this module can produce.
    ATTRIBUTED_BUT_UNAUTHORIZED = "ATTRIBUTED_BUT_UNAUTHORIZED"

    #: The boundary observed the write; no trusted lease was active. The act
    #: is known, the actor is not. A rejected identity claim lands here too:
    #: an untrusted claim yields no attribution, it does not yield a guess.
    DETECTED_BUT_UNATTRIBUTED = "DETECTED_BUT_UNATTRIBUTED"

    #: Operator regions changed on disk with no observation to explain it --
    #: a subprocess, another host, or a human editor. Reachable only through
    #: reconciliation; the in-process path can never produce it.
    OUTSIDE_OBSERVABLE_BOUNDARY = "OUTSIDE_OBSERVABLE_BOUNDARY"

    #: The classifier could not decide, most often because observation was
    #: not installed, so absence of a record proves nothing. Never emitted to
    #: stand in for a state that was merely inconvenient to determine.
    UNKNOWN = "UNKNOWN"


# The set of tokens this module has actually minted. Membership -- not the
# presence of a lease object -- is what makes an identity claim trustworthy,
# so a hand-constructed binding cannot pass, and a binding captured inside a
# `bind()` block stops passing the moment that block exits.
_MINTED: set[int] = set()


@dataclass(frozen=True)
class _Binding:
    lease: Any
    token: int


_ACTIVE: contextvars.ContextVar[_Binding | None] = contextvars.ContextVar(
    "atlas_human_content_lease", default=None
)


@contextmanager
def bind(lease: Any) -> Iterator[None]:
    """Bind ``lease`` to the current execution for the duration of the block.

    The token is minted on entry and destroyed on exit. Destroying it is what
    makes lease *loss* observable: a write that escapes the block -- deferred,
    queued, or run from a finaliser -- finds a binding whose token is no
    longer minted and is reported as unattributed rather than credited to a
    lease that had already ended.
    """
    # A live sentinel, because `id()` of a dead object can be reused and a
    # recycled address would let a stale binding pass as a minted one.
    sentinel = object()
    token_id = id(sentinel)
    _MINTED.add(token_id)
    reset = _ACTIVE.set(_Binding(lease=lease, token=token_id))
    try:
        yield
    finally:
        _ACTIVE.reset(reset)
        _MINTED.discard(token_id)
        del sentinel


def _authorized(lease: Any, dest: pathlib.Path) -> bool:
    """Is ``dest`` inside the lease's authorized scope?

    Forbidden wins over authorized. A lease with no authorized paths grants
    no write scope at all -- an empty allow-list is empty, not universal.
    """
    try:
        root = pathlib.Path(lease.worktree).resolve()
        target = dest.resolve()
    except (OSError, ValueError, TypeError):
        return False
    for entry in getattr(lease, "forbidden_paths", ()) or ():
        try:
            if target == (root / entry).resolve() or target.is_relative_to(
                (root / entry).resolve()
            ):
                return False
        except (OSError, ValueError):
            continue
    for entry in getattr(lease, "authorized_paths", ()) or ():
        try:
            allowed = (root / entry).resolve()
        except (OSError, ValueError):
            continue
        if target == allowed or target.is_relative_to(allowed):
            return True
    return False


def classify(dest: Any, *, observed: bool = True, installed: bool = True) -> Attribution:
    """Classify one protected write.

    ``observed`` says the boundary saw this write; ``installed`` says the
    boundary was watching at all. The two are kept separate on purpose --
    "nothing was seen" means nothing unless something was looking. That is the
    absence/liveness rule applied to attribution: silence is not evidence.
    """
    if not installed:
        return Attribution.UNKNOWN
    if not observed:
        return Attribution.OUTSIDE_OBSERVABLE_BOUNDARY
    binding = _ACTIVE.get()
    if binding is None or binding.token not in _MINTED:
        return Attribution.DETECTED_BUT_UNATTRIBUTED
    if not getattr(binding.lease, "active", True):
        return Attribution.DETECTED_BUT_UNATTRIBUTED
    try:
        path = pathlib.Path(dest)
    except (ValueError, TypeError):
        return Attribution.UNKNOWN
    if _authorized(binding.lease, path):
        return Attribution.GOVERNED_AND_ATTRIBUTED
    return Attribution.ATTRIBUTED_BUT_UNAUTHORIZED


@dataclass
class ProtectedWrite:
    """One protected write, with the authority context in force at the time."""

    path: str
    primitive: str
    altered: bool
    attribution: Attribution
    lease_id: str = ""
    agent_id: str = ""
    package_id: str = ""
    base_pin: str = ""

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        who = f"{self.agent_id}/{self.lease_id}" if self.lease_id else "-"
        state = "ALTERED" if self.altered else "intact"
        return f"{self.attribution.value} {state} {self.path} by {who}"


@dataclass
class AttributionLedger:
    """Every protected write seen, classified, plus what was *not* seen."""

    writes: list[ProtectedWrite] = field(default_factory=list)
    installed: bool = True

    def record(self, path: Any, primitive: str, *, altered: bool) -> ProtectedWrite:
        verdict = classify(path, observed=True, installed=self.installed)
        binding = _ACTIVE.get()
        trusted = binding is not None and binding.token in _MINTED
        lease = binding.lease if (binding is not None and trusted) else None
        entry = ProtectedWrite(
            path=str(path),
            primitive=primitive,
            altered=altered,
            attribution=verdict,
            lease_id=getattr(lease, "lease_id", "") if lease else "",
            agent_id=getattr(lease, "agent_id", "") if lease else "",
            package_id=getattr(lease, "package_id", "") if lease else "",
            base_pin=getattr(lease, "base_pin", "") if lease else "",
        )
        self.writes.append(entry)
        return entry

    def reconcile(self, before: dict[str, bytes], after: dict[str, bytes]) -> list[ProtectedWrite]:
        """Name changes on disk that no observation explains.

        This is the only producer of ``OUTSIDE_OBSERVABLE_BOUNDARY``. Without
        it that state would be decorative -- a vocabulary entry nothing could
        ever emit, which is a different way of hiding a gap.
        """
        seen = {os.path.realpath(w.path) for w in self.writes}
        escaped: list[ProtectedWrite] = []
        for path, prior in before.items():
            current = after.get(path)
            if current is None or current == prior:
                continue
            real = os.path.realpath(path)
            if real in seen:
                continue
            entry = ProtectedWrite(
                path=path,
                primitive="(unobserved)",
                altered=True,
                attribution=(
                    Attribution.OUTSIDE_OBSERVABLE_BOUNDARY
                    if self.installed
                    else Attribution.UNKNOWN
                ),
            )
            self.writes.append(entry)
            escaped.append(entry)
        return escaped

    def by_state(self) -> dict[str, int]:
        counts = {state.value: 0 for state in Attribution}
        for write in self.writes:
            counts[write.attribution.value] += 1
        return counts
