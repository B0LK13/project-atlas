"""Shared HUMAN-region preservation primitive (AT-011).

Atlas owns the generated region of a projected Markdown note; anything a
human wraps in a named ``<!-- BEGIN HUMAN: name --> ... <!-- END HUMAN: name
-->`` block survives a re-render byte-for-byte. This is the one
implementation of that contract -- both the living Obsidian project
projection (:mod:`project_atlas.obsidian_projection`) and the Obsidian
capture-note projection (:mod:`project_atlas.obsidian_capture_note`) call
into it, so the merge algorithm cannot drift between the two surfaces the
way the atomic-write layer already guards against for filesystem writes
(:mod:`project_atlas.capture_io`).

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
        return rendered
    validate_protected_markers(existing, path=path)
    validate_protected_markers(rendered, path=path)
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
