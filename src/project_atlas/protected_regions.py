"""Shared HUMAN-region preservation primitive (AT-011).

Atlas owns the generated region of a projected Markdown note; anything a
human wraps in a named ``<!-- BEGIN HUMAN: name --> ... <!-- END HUMAN: name
-->`` block survives a re-render byte-for-byte. Both the living Obsidian
project projection (:mod:`project_atlas.obsidian_projection`) and the
Obsidian capture-note projection (:mod:`project_atlas.obsidian_capture_note`)
call into it, so the merge algorithm cannot drift between those two surfaces
the way the atomic-write layer already guards against for filesystem writes
(:mod:`project_atlas.capture_io`).

This is **not** yet the only implementation in the repository:
:mod:`project_atlas.graph_projections` still carries its own private
``_merge_protected_regions``, which diverges here (it preserves text outside
the generated span when a note has no HUMAN regions, where this module
returns the fresh render). Consolidating the two is tracked separately;
until then, a change here does not automatically change graph projections.

Callers translate :class:`ProtectedRegionError` into their own domain error
type at the boundary (the existing convention in this codebase for
``ValueError``-raising primitives such as ``ensure_under_root``), so this
module carries no dependency on either caller's error vocabulary.
"""

from __future__ import annotations

import re
from collections import Counter

GENERATED_START = "<!-- atlas:generated:start -->"
GENERATED_END = "<!-- atlas:generated:end -->"
_HUMAN_BEGIN = re.compile(r"<!--\s*BEGIN HUMAN:\s*([^\s>]+)\s*-->")
_HUMAN_END = re.compile(r"<!--\s*END HUMAN:\s*([^\s>]+)\s*-->")


class ProtectedRegionError(ValueError):
    """Fail-closed: malformed generated/human region markers."""


def validate_protected_markers(text: str, *, path: str) -> None:
    begins = _HUMAN_BEGIN.findall(text)
    ends = _HUMAN_END.findall(text)
    if len(begins) != len(ends) or sorted(begins) != sorted(ends):
        raise ProtectedRegionError(f"malformed-protected-markers:{path}")
    start_count = text.count(GENERATED_START)
    end_count = text.count(GENERATED_END)
    if start_count != end_count or start_count > 1:
        raise ProtectedRegionError(f"malformed-generated-markers:{path}")
    if start_count == 1 and text.index(GENERATED_END) < text.index(GENERATED_START):
        raise ProtectedRegionError(f"malformed-generated-markers:{path}")


#: A region's identity: the names of its open ancestors, outermost first,
#: followed by its own name. ``a/x`` and ``b/x`` are therefore two different
#: regions rather than one name used twice.
RegionPath = tuple[str, ...]


def _human_region_spans(text: str) -> list[tuple[RegionPath, int, int]]:
    """``(path, start, end)`` for every HUMAN block, in document order.

    Markers are paired structurally with a stack rather than by searching for
    the next ``END`` of the same name, so a region's identity is its position
    in the nesting tree. Anything that cannot be paired unambiguously fails
    closed here, which is the only way a caller can be handed a document it is
    safe to rewrite:

    * an ``END`` with no open region, or one that does not close the innermost
      open region -- crossed markers such as ``BEGIN a, BEGIN b, END a, END b``
      have no single valid reading;
    * a ``BEGIN`` left open at end of document;
    * a region whose name equals one of its own open ancestors. Its path would
      be unique, but the marker text is not: nothing in the document says which
      ``END`` closes which ``BEGIN``, so the structure is ambiguous to any
      reader, human or otherwise.
    """
    events: list[tuple[int, int, str, int]] = []
    for match in _HUMAN_BEGIN.finditer(text):
        events.append((match.start(), 0, match.group(1), match.end()))
    for match in _HUMAN_END.finditer(text):
        events.append((match.start(), 1, match.group(1), match.end()))
    events.sort(key=lambda event: event[0])

    spans: list[tuple[RegionPath, int, int]] = []
    open_stack: list[tuple[str, int]] = []
    open_names: Counter[str] = Counter()
    for position, kind, name, marker_end in events:
        if kind == 0:
            if name in open_names:
                raise ProtectedRegionError(
                    f"ambiguous-protected-region-nesting:{name}"
                )
            open_stack.append((name, position))
            open_names[name] += 1
            continue
        if not open_stack or open_stack[-1][0] != name:
            raise ProtectedRegionError(f"malformed-protected-markers:unpaired:{name}")
        open_name, open_position = open_stack.pop()
        del open_names[open_name]
        region = (*(ancestor for ancestor, _ in open_stack), name)
        spans.append((region, open_position, marker_end))
    if open_stack:
        raise ProtectedRegionError(
            f"malformed-protected-markers:missing-end:{open_stack[-1][0]}"
        )
    spans.sort(key=lambda span: span[1])
    return spans


def _ambiguous_region_paths(spans: list[tuple[RegionPath, int, int]]) -> list[str]:
    """Paths used by more than one region in ``spans``.

    Scope is part of identity, so this is the only remaining ambiguity once
    :func:`_human_region_spans` has accepted the structure: two regions that
    genuinely occupy the same slot. ``a/x`` beside ``b/x`` is not one of them.
    """
    counts = Counter(path for path, _, _ in spans)
    return sorted("/".join(path) for path, seen in counts.items() if seen > 1)


def reject_ambiguous_region_identity(text: str, *, path: str) -> None:
    """Fail closed when HUMAN region identity is ambiguous.

    A region's name is its identity. :func:`extract_human_regions` keys blocks
    by name, so before this check a second block of the same name silently
    overwrote the first and a re-render dropped human-authored content with no
    error and no diagnostic.

    Owner policy is to refuse rather than choose: no first-wins, no last-wins,
    no concatenation, no reordering. Content equality does not disambiguate --
    the ambiguity is in the identity, not the payload -- so identical and empty
    duplicates are refused too. Names are compared exactly, matching the
    identity contract the merge itself uses, so ``Notes`` and ``notes`` are two
    different regions rather than a duplicate.

    What counts as ambiguous is decided structurally by
    :func:`_ambiguous_region_names`, which is what keeps this an F1 identity
    verdict rather than a ruling on nesting: nested *same-name* regions are
    refused, nested *distinct-name* documents keep the behaviour they had
    before F1 existed, at every generation rather than only the first.
    """
    duplicates = _ambiguous_region_paths(_human_region_spans(text))
    if duplicates:
        raise ProtectedRegionError(
            f"duplicate-protected-region-names:{','.join(duplicates)}:{path}"
        )


def extract_human_regions(text: str) -> dict[RegionPath, str]:
    """HUMAN blocks keyed by structural path, outermost ancestor first.

    Keyed by :data:`RegionPath` rather than by bare name: ``a/x`` and ``b/x``
    are independent regions, and collapsing them into one dictionary slot is
    what silently discarded one of them. A block's bytes include everything
    nested inside it, so a parent's entry already carries its children.

    Fails closed on ambiguous identity for the same reason the merge does:
    this function is exported and callable on its own, and quietly returning
    one of two regions that claim the same slot is exactly the human-data loss
    this module exists to prevent.
    """
    spans = _human_region_spans(text)
    duplicates = _ambiguous_region_paths(spans)
    if duplicates:
        raise ProtectedRegionError(
            f"duplicate-protected-region-names:{','.join(duplicates)}:extract"
        )
    return {path: text[start:end] for path, start, end in spans}


def merge_protected_regions(*, existing: str | None, rendered: str, path: str) -> str:
    """Splice HUMAN blocks from ``existing`` into a fresh ``rendered``.

    ``existing is None`` (first write, no prior file) returns ``rendered``
    unchanged. Otherwise every HUMAN block in ``existing`` is re-inserted at
    the position in ``rendered`` holding the **same structural path** --
    byte-for-byte, never re-derived from the new render, and never moved into
    a different scope. A block whose path the fresh render no longer offers is
    appended rather than dropped.

    Resolution is by path, not by name. Keying on the bare name collapsed
    ``a/x`` and ``b/x`` into one slot, so the last one parsed won and its bytes
    were then spliced into the *other* container -- one human's note silently
    replaced by another's. Position is used only to locate spans; it is never
    identity, so reordering two sibling containers moves nothing between them.

    The whole plan is resolved and validated before a single byte is written.
    If any identity is ambiguous the caller gets an exception and the note it
    passed in is untouched -- there is no partially rewritten result.
    """
    if existing is None:
        validate_protected_markers(rendered, path=path)
        reject_ambiguous_region_identity(rendered, path=path)
        return rendered
    validate_protected_markers(existing, path=path)
    validate_protected_markers(rendered, path=path)

    existing_spans = _human_region_spans(existing)
    rendered_spans = _human_region_spans(rendered)
    for spans in (existing_spans, rendered_spans):
        duplicates = _ambiguous_region_paths(spans)
        if duplicates:
            raise ProtectedRegionError(
                f"duplicate-protected-region-names:{','.join(duplicates)}:{path}"
            )

    prior = {region: existing[start:end] for region, start, end in existing_spans}
    if not prior:
        return rendered

    # Plan. Outermost match wins: a block's bytes already contain everything
    # nested inside it, so replacing a parent also restores its children, and
    # descending into it afterwards would splice the same content twice.
    replacements: list[tuple[int, int, str]] = []
    replaced: list[RegionPath] = []
    covered_until = -1
    for region, start, end in rendered_spans:
        if start < covered_until or region not in prior:
            continue
        replacements.append((start, end, prior[region]))
        replaced.append(region)
        covered_until = end

    def _is_under(candidate: RegionPath, ancestor: RegionPath) -> bool:
        return candidate[: len(ancestor)] == ancestor

    # A prior region the fresh render has no slot for is appended, so human
    # bytes survive a template that dropped its section. Only the outermost
    # such region is appended: its block already carries its descendants.
    orphans = [
        region
        for region in sorted(prior)
        if not any(_is_under(region, done) for done in replaced)
    ]
    minimal_orphans = [
        region
        for region in orphans
        if not any(other != region and _is_under(region, other) for other in orphans)
    ]

    merged = rendered
    for start, end, block in sorted(replacements, reverse=True):
        merged = merged[:start] + block + merged[end:]
    for region in minimal_orphans:
        merged = merged.rstrip() + "\n\n" + prior[region] + "\n"

    validate_protected_markers(merged, path=path)
    reject_ambiguous_region_identity(merged, path=path)
    return merged
