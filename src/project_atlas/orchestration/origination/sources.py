"""Origination source declarations -- SOURCE_AUTHORITY = EXPLICIT.

D-PHASE2A-RETRY: ``adapter.py``'s ``eligible_roadmap_items()`` reads
exactly one, fixed, hard-coded location (``docs/ROADMAP.md``) in one
fixed, structured format. That is still fully supported -- unchanged,
still the default when a project declares no explicit configuration
(backward compatible with every existing caller and every existing
test). This module adds a second axis: a project may explicitly declare
one or more additional origination sources, each in a named format, via
its own ``.atlas-project.yaml`` marker:

    origination_sources:
      - path: docs/ROADMAP.md
        format: structured-roadmap
      - path: docs/backlog.md
        format: markdown-task-list

A source becomes authoritative *only* through this explicit declaration
(or the pre-existing, always-on ``docs/ROADMAP.md`` default) -- never by
scanning every Markdown checkbox in a repository. A README checklist, a
tutorial's steps, an issue template, or any file a project has not
declared is never treated as engineering work, regardless of its
checkbox syntax.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.orchestration.origination.acceptance_contracts import (
    apply_acceptance_contracts,
    load_acceptance_contracts,
)
from project_atlas.orchestration.origination.adapter import (
    EligibleRoadmapItem,
    eligible_roadmap_items,
)
from project_atlas.orchestration.origination.tasklist_adapter import eligible_task_list_items

_MARKER_NAMES: tuple[str, ...] = (".atlas-project.yaml", ".atlas/project.yaml")
_REL_PATH_MAX = 256


class OriginationSourceFormat(StrEnum):
    """Closed vocabulary. A third format is a deliberate future extension,
    never silently inferred from a file's own contents or extension."""

    STRUCTURED_ROADMAP = "structured-roadmap"
    MARKDOWN_TASK_LIST = "markdown-task-list"


class OriginationSourceConfig(BaseModel):
    """One explicitly declared origination source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1, max_length=_REL_PATH_MAX)
    format: OriginationSourceFormat

    @field_validator("path")
    @classmethod
    def _safe_relative_path(cls, value: str) -> str:
        posix = value.replace("\\", "/")
        if posix.startswith("./"):
            posix = posix[2:]
        if not posix or posix.startswith("/") or ".." in posix.split("/"):
            raise ValueError("origination source path must be a safe relative path")
        return posix


#: The pre-existing, always-on default: a project declaring no explicit
#: ``origination_sources`` configuration at all still gets exactly the
#: original, sole behavior (docs/ROADMAP.md, structured-roadmap format) --
#: full backward compatibility for every project and every existing test.
DEFAULT_SOURCES: tuple[OriginationSourceConfig, ...] = (
    OriginationSourceConfig(
        path="docs/ROADMAP.md", format=OriginationSourceFormat.STRUCTURED_ROADMAP
    ),
)


class OriginationSourceConfigError(ValueError):
    """A ``.atlas-project.yaml`` origination_sources block is malformed.

    Fails closed: an unreadable or invalid declaration never silently
    falls back to "no sources" or "scan everything" -- the caller must
    see the error, exactly like every other explicit-authority contract
    in this package.
    """


def _find_marker(project_root: Path) -> Path | None:
    for name in _MARKER_NAMES:
        candidate = project_root / name
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    return None


def load_origination_sources(project_root: Path) -> tuple[OriginationSourceConfig, ...]:
    """Return the explicitly declared origination sources for a project,
    or :data:`DEFAULT_SOURCES` when none are declared.

    Never raises for a missing marker or a marker with no
    ``origination_sources`` key -- both are the honest, common "this
    project has not opted into the generic model yet" case, preserved as
    the original single-source behavior. Raises
    :class:`OriginationSourceConfigError` only when the key *is* present
    but malformed -- an explicit declaration that cannot be understood
    must fail closed, not silently ignore itself.
    """
    marker = _find_marker(project_root)
    if marker is None:
        return DEFAULT_SOURCES
    try:
        raw = yaml.safe_load(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise OriginationSourceConfigError(f"unreadable project marker: {marker}") from exc
    if raw is None:
        # An entirely empty marker file. Genuinely no configuration at
        # all -- indistinguishable from "no marker", the honest default
        # case.
        return DEFAULT_SOURCES
    if not isinstance(raw, dict):
        # PR-A review finding (chatgpt-codex-connector, P2): a marker that
        # parses to a scalar or a list is not "no configuration" -- it is
        # a marker that failed to parse as the mapping this project's own
        # `.atlas-project.yaml`/`.atlas/project.yaml` contract requires
        # (a templating error, a merge conflict marker left in place, an
        # accidentally-truncated file). Silently falling back to
        # DEFAULT_SOURCES here could make docs/ROADMAP.md authoritative
        # again even though a project actually intended to declare
        # something else -- fail closed instead.
        raise OriginationSourceConfigError(
            f"project marker must parse to a mapping, got {type(raw).__name__}: {marker}"
        )
    if "origination_sources" not in raw:
        return DEFAULT_SOURCES
    declared = raw["origination_sources"]
    if not isinstance(declared, list) or not declared:
        # Catches both a genuinely malformed shape (a mapping/scalar where
        # a list was expected) and the explicit `origination_sources:`
        # (null) case the same review finding flagged: a present-but-empty
        # key is a declaration that failed to say anything meaningful,
        # not an absent one -- it must not silently resolve to the
        # unrelated DEFAULT_SOURCES behavior.
        raise OriginationSourceConfigError(
            f"origination_sources must be a non-empty list in {marker}"
        )
    sources: list[OriginationSourceConfig] = []
    seen_declarations: set[tuple[str, str]] = set()
    for index, entry in enumerate(declared):
        if not isinstance(entry, dict):
            raise OriginationSourceConfigError(
                f"origination_sources[{index}] must be a mapping in {marker}"
            )
        try:
            source = OriginationSourceConfig.model_validate(entry)
        except Exception as exc:  # pydantic ValidationError, kept generic at this boundary
            raise OriginationSourceConfigError(
                f"origination_sources[{index}] is invalid in {marker}: {exc}"
            ) from exc
        # PR-A review finding (chatgpt-codex-connector, P2): the same
        # (path, format) pair declared twice would scan the same file
        # twice, inflating eligible_count and redundantly re-attempting
        # proposal/materialization for identical items in a single scan.
        # SOURCE_AUTHORITY = EXPLICIT means an ambiguous/redundant
        # declaration should be rejected, not silently accepted or
        # silently de-duplicated (silent de-duplication would hide a real
        # authoring mistake from the project maintaining this config).
        declaration_key = (source.path, source.format.value)
        if declaration_key in seen_declarations:
            raise OriginationSourceConfigError(
                f"origination_sources[{index}] duplicates an earlier declaration "
                f"of {source.path!r} ({source.format.value}) in {marker}"
            )
        seen_declarations.add(declaration_key)
        sources.append(source)
    return tuple(sources)


def _items_for(
    project_root: Path, source: OriginationSourceConfig
) -> tuple[EligibleRoadmapItem, ...]:
    if source.format is OriginationSourceFormat.STRUCTURED_ROADMAP:
        if source.path != "docs/ROADMAP.md":
            # eligible_roadmap_items() reads exactly this one fixed
            # location today; a structured-roadmap declaration at any
            # other path is not yet supported by the underlying parser.
            # Fail closed rather than silently reading the wrong file or
            # silently ignoring the declaration.
            raise OriginationSourceConfigError(
                "structured-roadmap format is only supported at docs/ROADMAP.md "
                f"(declared: {source.path!r})"
            )
        return eligible_roadmap_items(project_root)
    if source.format is OriginationSourceFormat.MARKDOWN_TASK_LIST:
        return eligible_task_list_items(project_root, source.path)
    # pragma: no cover -- StrEnum exhausts both members above; a third
    # format is a deliberate future extension, not a reachable branch.
    raise AssertionError(f"unhandled origination source format: {source.format!r}")


class DuplicateItemIdError(ValueError):
    """The same stable item_id is declared authoritative by two different
    origination sources. Fails closed rather than silently preferring
    one -- an ambiguous identity is not a safe thing to originate work
    from (mirrors this package's other identity-collision fail-closed
    contracts, e.g. AS-ID-001's ambiguous-subject handling)."""


def eligible_work_items(project_root: Path) -> tuple[EligibleRoadmapItem, ...]:
    """The generic, multi-source successor to
    :func:`~project_atlas.orchestration.origination.adapter.
    eligible_roadmap_items`: read every explicitly declared origination
    source (or the single default source, unchanged, when none are
    declared) and return every eligible item across all of them.

    Never raises for the sourcing itself being empty or absent -- an
    empty tuple is the correct, honest ``NO_ELIGIBLE_WORK`` outcome.
    Raises :class:`OriginationSourceConfigError` for a malformed explicit
    declaration, :class:`DuplicateItemIdError` for the same item_id
    declared by two different sources, and :class:`~project_atlas.
    orchestration.origination.acceptance_contracts.
    AcceptanceContractConfigError` for a malformed, ambiguous, or
    unmatched acceptance-contract declaration -- all are real
    configuration problems that must be visible, not silently resolved
    one way or the other.

    AS-ORIGIN-ACCEPTANCE-001 (PR-D): after collecting every eligible
    item across every declared source (unchanged from before this
    field existed), any explicitly declared acceptance contracts
    (``acceptance_contracts.py``) are merged in as the last step, before
    returning -- widening what evidence/scope/criteria an item carries,
    never changing which items are eligible or what their blockers/
    dependencies are.
    """
    sources = load_origination_sources(project_root)
    items: list[EligibleRoadmapItem] = []
    seen: dict[str, str] = {}
    for source in sources:
        for item in _items_for(project_root, source):
            existing_source = seen.get(item.item_id)
            if existing_source is not None and existing_source != item.source_path:
                raise DuplicateItemIdError(
                    f"item_id {item.item_id!r} is declared by both "
                    f"{existing_source!r} and {item.source_path!r}"
                )
            seen[item.item_id] = item.source_path
            items.append(item)
    contracts = load_acceptance_contracts(project_root)
    if not contracts:
        return tuple(items)
    return apply_acceptance_contracts(tuple(items), contracts)


__all__ = [
    "DEFAULT_SOURCES",
    "DuplicateItemIdError",
    "OriginationSourceConfig",
    "OriginationSourceConfigError",
    "OriginationSourceFormat",
    "eligible_work_items",
    "load_origination_sources",
]
