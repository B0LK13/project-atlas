"""D-087 in-memory path relationship helpers for estate discovery.

Filesystem paths are resolved and safety-validated at the traversal boundary.
After a path is accepted as inside the authorized estate, project/knowledge
relationship matching uses already-canonical keys and must not call
``Path.resolve`` merely to ask whether path A is beneath path B.

These helpers are component-aware. Naive string prefix matching is forbidden:

    ``d:/foo`` is not an ancestor of ``d:/foobar``.

Untrusted / external paths must still go through ``canonical_path_key`` and
``_under_authorized`` in ``estate_discovery``.
"""

from __future__ import annotations

import os
import sys
import time
import unicodedata
from collections.abc import Iterable, Iterator, Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path


def _casefold_paths() -> bool:
    return os.name == "nt" or sys.platform == "darwin"


@dataclass
class DiscoveryPerf:
    """Bounded, non-authoritative discovery operation counters and phases.

    Timings are diagnostic only. They are never canonical truth.
    """

    path_resolve_calls: int = 0
    canonical_path_key_calls: int = 0
    under_authorized_calls: int = 0
    knowledge_project_ancestry_checks: int = 0
    git_boundary_checks: int = 0
    filesystem_stat_calls: int = 0
    project_fingerprint_builds: int = 0
    phases: dict[str, float] = field(default_factory=dict)

    def add_phase(self, name: str, seconds: float) -> None:
        self.phases[name] = round(float(seconds), 6)

    def bump_phase(self, name: str, seconds: float) -> None:
        self.phases[name] = round(self.phases.get(name, 0.0) + float(seconds), 6)

    def counters(self) -> dict[str, int]:
        return {
            "path_resolve_calls": self.path_resolve_calls,
            "canonical_path_key_calls": self.canonical_path_key_calls,
            "under_authorized_calls": self.under_authorized_calls,
            "knowledge_project_ancestry_checks": self.knowledge_project_ancestry_checks,
            "git_boundary_checks": self.git_boundary_checks,
            "filesystem_stat_calls": self.filesystem_stat_calls,
            "project_fingerprint_builds": self.project_fingerprint_builds,
        }

    def snapshot(self) -> dict[str, int]:
        return dict(self.counters())


_PERF = DiscoveryPerf()


def reset_discovery_perf() -> DiscoveryPerf:
    global _PERF
    _PERF = DiscoveryPerf()
    return _PERF


def current_discovery_perf() -> DiscoveryPerf:
    return _PERF


class _PhaseTimer:
    def __init__(self, name: str, *, accumulate: bool = False) -> None:
        self._name = name
        self._accumulate = accumulate
        self._start = 0.0

    def __enter__(self) -> DiscoveryPerf:
        self._start = time.perf_counter()
        return _PERF

    def __exit__(self, *exc: object) -> None:
        elapsed = time.perf_counter() - self._start
        if self._accumulate:
            _PERF.bump_phase(self._name, elapsed)
        else:
            _PERF.add_phase(self._name, elapsed)


def phase_timer(name: str, *, accumulate: bool = False) -> _PhaseTimer:
    return _PhaseTimer(name, accumulate=accumulate)


def canonical_key_from_resolved_text(resolved_text: str) -> str:
    """Canonical key from an already-resolved path string. No filesystem I/O."""
    _PERF.canonical_path_key_calls += 1
    text = unicodedata.normalize("NFC", resolved_text.replace("\\", "/"))
    if _casefold_paths():
        return text.casefold()
    return text


def canonical_path_key_resolved(resolved_path: Path) -> str:
    """Canonical key for a path that is already resolved. No ``Path.resolve``."""
    return canonical_key_from_resolved_text(resolved_path.as_posix())


def parent_canonical_key(path_key: str) -> str:
    """Immediate parent of a canonical path key. No filesystem I/O."""
    if not path_key or path_key == "/":
        return ""
    stripped = path_key.rstrip("/")
    if not stripped or stripped == "/":
        return ""
    if len(stripped) == 2 and stripped[1] == ":":
        return ""
    if "/" not in stripped:
        return ""
    parent = stripped.rsplit("/", 1)[0]
    if parent == "":
        return "/"
    return parent


def iter_strict_ancestor_keys(path_key: str) -> Iterator[str]:
    """Yield parent keys from nearest parent to the volume/filesystem root."""
    current = parent_canonical_key(path_key)
    while current:
        yield current
        current = parent_canonical_key(current)


def is_canonical_descendant(child_key: str, ancestor_key: str) -> bool:
    """True when ``child_key`` is a strict component-aware descendant."""
    if not child_key or not ancestor_key:
        return False
    child = child_key.rstrip("/") if child_key != "/" else child_key
    ancestor = ancestor_key.rstrip("/") if ancestor_key != "/" else ancestor_key
    if child == ancestor:
        return False
    return child.startswith(ancestor + "/")


def is_canonical_under(child_key: str, root_key: str) -> bool:
    """True when ``child_key`` equals or is a component-aware descendant of root."""
    if not child_key or not root_key:
        return False
    child = child_key.rstrip("/") if child_key != "/" else child_key
    root = root_key.rstrip("/") if root_key != "/" else root_key
    if child == root:
        return True
    return child.startswith(root + "/")


def estate_region_resolved(resolved_path: Path, root_resolved: Path) -> str:
    """First relative component. Both paths must already be resolved."""
    try:
        rel = resolved_path.relative_to(root_resolved)
    except ValueError:
        return "_outside"
    parts = rel.parts
    if not parts or parts == (".",):
        return "_root"
    return str(parts[0])


def has_selected_project_ancestor(
    path_key: str,
    project_keys: Iterable[str],
    *,
    count: bool = True,
) -> bool:
    """O(depth) membership: any selected project is a strict ancestor."""
    keys = project_keys if isinstance(project_keys, (set, frozenset)) else set(project_keys)
    for ancestor in iter_strict_ancestor_keys(path_key):
        if count:
            _PERF.knowledge_project_ancestry_checks += 1
        if ancestor in keys:
            return True
    return False


def ancestor_items_from_index[T](
    path_key: str,
    by_key: Mapping[str, T],
    *,
    count: bool = True,
) -> list[T]:
    """O(depth) collect selected projects that strictly enclose ``path_key``."""
    found: list[T] = []
    for ancestor in iter_strict_ancestor_keys(path_key):
        if count:
            _PERF.knowledge_project_ancestry_checks += 1
        item = by_key.get(ancestor)
        if item is not None:
            found.append(item)
    return found


def candidate_path_key_from_record(record: Mapping[str, object] | object) -> str | None:
    """Read a stored path_key from a candidate / fingerprint. No resolve."""
    fingerprint: object
    if isinstance(record, Mapping):
        stored = record.get("path_key")
        if isinstance(stored, str) and stored:
            return stored
        fingerprint = record.get("fingerprint")
    else:
        stored = getattr(record, "path_key", None)
        if isinstance(stored, str) and stored:
            return stored
        fingerprint = getattr(record, "fingerprint", None)
    if isinstance(fingerprint, MutableMapping):
        key = fingerprint.get("path_key")
        if isinstance(key, str) and key:
            return key
    return None


__all__ = [
    "DiscoveryPerf",
    "ancestor_items_from_index",
    "candidate_path_key_from_record",
    "canonical_key_from_resolved_text",
    "canonical_path_key_resolved",
    "current_discovery_perf",
    "estate_region_resolved",
    "has_selected_project_ancestor",
    "is_canonical_descendant",
    "is_canonical_under",
    "iter_strict_ancestor_keys",
    "parent_canonical_key",
    "phase_timer",
    "reset_discovery_perf",
]
