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


def reject_ambiguous_region_identity(text: str, *, path: str) -> None:
    """Fail closed when two HUMAN regions in one document share a name.

    A region's name is its identity. The fresh render has one slot per name,
    so two blocks answering to the same name give no way to say which slot
    owns which block. :func:`extract_human_regions` keys blocks by name, so
    before this check the later block silently overwrote the earlier one and a
    re-render dropped human-authored content with no error and no diagnostic.

    Owner policy is to refuse rather than choose: no first-wins, no last-wins,
    no concatenation, no reordering. Content equality does not disambiguate --
    the ambiguity is in the identity, not the payload -- so identical and empty
    duplicates are refused too. Names are compared exactly, matching the
    identity contract the merge itself uses, so ``Notes`` and ``notes`` are two
    different regions rather than a duplicate.

    **Scope: this is applied to the merge's *inputs* only, never to its
    output.** Nested regions with *distinct* names legitimately produce a
    merged document carrying the inner block twice; whether that nesting
    behaviour is correct is a separate open question, and running this check
    over the merged text would answer it by refusing every nested document.
    Nested *same-name* regions are still refused here, because their identity
    is ambiguous for exactly the reason above -- that is an F1 ambiguity
    verdict, not a general ruling on nesting.
    """
    counts = Counter(_HUMAN_BEGIN.findall(text))
    duplicates = sorted(name for name, seen in counts.items() if seen > 1)
    if duplicates:
        raise ProtectedRegionError(
            f"duplicate-protected-region-names:{','.join(duplicates)}:{path}"
        )


def extract_human_regions(text: str) -> dict[str, str]:
    regions: dict[str, str] = {}
    for match in _HUMAN_BEGIN.finditer(text):
        name = match.group(1)
        end_match = re.search(
            rf"<!--\s*END HUMAN:\s*{re.escape(name)}\s*-->",
            text[match.end() :],
        )
        if end_match is None:
            raise ProtectedRegionError(f"malformed-protected-markers:missing-end:{name}")
        if name in regions:
            # Unreachable through merge_protected_regions, which runs
            # reject_ambiguous_region_identity over its inputs first. Kept
            # because this function is exported and callable on its own, and
            # silently dropping a block here is exactly the human-data loss
            # this module exists to prevent.
            raise ProtectedRegionError(
                f"duplicate-protected-region-names:{name}:extract"
            )
        regions[name] = text[match.start() : match.end() + end_match.end()]
    return regions


def merge_protected_regions(*, existing: str | None, rendered: str, path: str) -> str:
    """Splice named HUMAN blocks from ``existing`` into a fresh ``rendered``.

    ``existing is None`` (first write, no prior file) returns ``rendered``
    unchanged. Otherwise every ``BEGIN HUMAN: name`` block found in
    ``existing`` is re-inserted at the same named position in ``rendered``
    (or appended, if the fresh render dropped that section) -- byte-for-byte,
    never re-derived from the new render.
    """
    if existing is None:
        validate_protected_markers(rendered, path=path)
        reject_ambiguous_region_identity(rendered, path=path)
        return rendered
    validate_protected_markers(existing, path=path)
    validate_protected_markers(rendered, path=path)
    # Inputs only -- see reject_ambiguous_region_identity on why the merged
    # result is deliberately not checked for duplicate names.
    reject_ambiguous_region_identity(existing, path=path)
    reject_ambiguous_region_identity(rendered, path=path)
    prior_humans = extract_human_regions(existing)
    if not prior_humans:
        return rendered
    merged = rendered
    for name, block in sorted(prior_humans.items()):
        pattern = re.compile(
            rf"<!--\s*BEGIN HUMAN:\s*{re.escape(name)}\s*-->.*?<!--\s*END HUMAN:\s*"
            rf"{re.escape(name)}\s*-->",
            re.DOTALL,
        )
        if not pattern.search(merged):
            merged = merged.rstrip() + "\n\n" + block + "\n"
        else:

            def _replacer(_match: re.Match[str], *, _block: str = block) -> str:
                return _block

            merged = pattern.sub(_replacer, merged, count=1)
    validate_protected_markers(merged, path=path)
    return merged
