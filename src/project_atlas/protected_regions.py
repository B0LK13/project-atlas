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


def _human_region_spans(text: str) -> list[tuple[str, int, int]]:
    """``(name, start, end)`` for every HUMAN block, in document order.

    Span end is the first ``END HUMAN: <name>`` after the begin, which is the
    same rule :func:`extract_human_regions` uses -- the two must agree or the
    ambiguity verdict would be about a different document than the merge.
    """
    spans: list[tuple[str, int, int]] = []
    for match in _HUMAN_BEGIN.finditer(text):
        name = match.group(1)
        end_match = re.search(
            rf"<!--\s*END HUMAN:\s*{re.escape(name)}\s*-->",
            text[match.end() :],
        )
        if end_match is None:
            raise ProtectedRegionError(f"malformed-protected-markers:missing-end:{name}")
        spans.append((name, match.start(), match.end() + end_match.end()))
    return spans


def _ambiguous_region_names(text: str) -> list[str]:
    """Names whose identity is genuinely ambiguous in ``text``.

    Two situations, and only these two:

    * **the same name appears twice at the same level** -- siblings, however
      far apart, empty or not, identical content or not. The fresh render has
      one slot per name and there is no way to say which block owns it.
    * **a region contains another region of its own name.** The inner block's
      identity is indistinguishable from its container's.

    Deliberately *not* ambiguous: a name that appears once at the top level
    and once inside a region with a **different** name. That is the shape a
    nested distinct-name document takes after one merge -- the merge appends
    the inner block alongside the outer block that already contains it -- and
    it is an artifact of the existing nesting behaviour, not an F1 identity
    conflict. Counting raw name occurrences cannot tell the two apart, so it
    refused a document the merge itself had just produced: the first render
    succeeded and the second failed. Whether that nesting behaviour is right
    is the open F2 question, and refusing it here would answer it by
    side effect.

    Containment is resolved with a stack over spans already in document
    order, so each span is pushed and popped once: linear in the number of
    regions, like the plain count it replaces. Comparing every span against
    every other would be quadratic, and this runs on every merge.
    """
    ambiguous: set[str] = set()
    root_siblings: set[str] = set()
    # (name, span end, names of the regions directly inside this one)
    open_spans: list[tuple[str, int, set[str]]] = []
    for name, start, end in _human_region_spans(text):
        while open_spans and open_spans[-1][1] <= start:
            open_spans.pop()
        if any(ancestor == name for ancestor, _, _ in open_spans):
            ambiguous.add(name)  # a region nested inside one of its own name
        else:
            # Siblings are compared within their own scope, at every depth --
            # not only at the top level. Two same-name blocks inside a
            # differently-named container are as ambiguous as two at the root:
            # extract_human_regions keys by name, so one of them is silently
            # dropped either way. Checking only the root left that fail-open.
            siblings = open_spans[-1][2] if open_spans else root_siblings
            if name in siblings:
                ambiguous.add(name)  # two blocks of this name in one scope
            siblings.add(name)
        open_spans.append((name, end, set()))
    return sorted(ambiguous)


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
    duplicates = _ambiguous_region_names(text)
    if duplicates:
        raise ProtectedRegionError(
            f"duplicate-protected-region-names:{','.join(duplicates)}:{path}"
        )


def extract_human_regions(text: str) -> dict[str, str]:
    """Named HUMAN blocks, keyed by name.

    Refuses ambiguous identity for the same reason the merge does: this
    function is exported and callable on its own, and silently dropping a
    block is exactly the human-data loss this module exists to prevent.

    A name that also appears nested inside a differently-named region is not
    ambiguous, and the later occurrence wins, which is the behaviour that
    predates F1. Changing it would alter what a nested distinct-name document
    renders to, which is an F2 decision this must not make.
    """
    duplicates = _ambiguous_region_names(text)
    if duplicates:
        raise ProtectedRegionError(
            f"duplicate-protected-region-names:{','.join(duplicates)}:extract"
        )
    regions: dict[str, str] = {}
    for match in _HUMAN_BEGIN.finditer(text):
        name = match.group(1)
        end_match = re.search(
            rf"<!--\s*END HUMAN:\s*{re.escape(name)}\s*-->",
            text[match.end() :],
        )
        if end_match is None:
            raise ProtectedRegionError(f"malformed-protected-markers:missing-end:{name}")
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
