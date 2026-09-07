"""AS-OBSIDIAN-CAPTURE-001-F3: Atlas marker spellings are reserved everywhere.

Owner decision (2026-09-07): the exact Atlas structural marker spelling is
reserved syntax wherever it appears, **including inside a HUMAN region**. The
rejected alternative was treating HUMAN payload as opaque, which would have
undone F2's nested-region structure and imported an anti-forgery obligation.

Current runtime already behaved this way. Nothing asserted it -- in particular
nothing asserted the *permissive* half, that near-misses and bare tokens stay
ordinary text. These tests pin the policy so it is enforced rather than
incidental, and so a future parser change cannot quietly widen or narrow it.

The invariant that matters most is the last column: every refusal leaves the
operator's note byte-identical. F3 is an availability defect, not data loss,
and it must stay that way.
"""
from __future__ import annotations

import pytest

from project_atlas.protected_regions import (
    GENERATED_END,
    GENERATED_START,
    ProtectedRegionError,
    merge_protected_regions,
)

PATH = "projects/p/note.md"


def _note(human_body: str, *, gen: str = "old generated body") -> str:
    return (
        f"{GENERATED_START}\n{gen}\n{GENERATED_END}\n\n"
        f"<!-- BEGIN HUMAN: notes -->\n{human_body}\n<!-- END HUMAN: notes -->\n"
    )


def _render(gen: str = "new generated body") -> str:
    return (
        f"{GENERATED_START}\n{gen}\n{GENERATED_END}\n\n"
        "<!-- BEGIN HUMAN: notes -->\n\n<!-- END HUMAN: notes -->\n"
    )


RESERVED = [
    pytest.param(f"note {GENERATED_START} here", id="exact-generated-start"),
    pytest.param(f"note {GENERATED_END} here", id="exact-generated-end"),
    pytest.param(f"a {GENERATED_START} b {GENERATED_END} c", id="both-exact-markers"),
    pytest.param(f"a\r\n{GENERATED_START}\r\nb", id="crlf-around-exact-marker"),
    pytest.param(f"éè {GENERATED_START} 你好", id="unicode-around-exact-marker"),
]

ORDINARY = [
    pytest.param("note atlas:generated:start here", id="bare-token-no-comment-syntax"),
    pytest.param("note <!--  atlas:generated:start  --> here", id="near-miss-extra-spaces"),
    pytest.param("note <!-- atlas:generated:startx --> here", id="near-miss-suffixed-name"),
    pytest.param("note <!-- atlas:generated:sta rt --> here", id="near-miss-split-token"),
    pytest.param("ordinary prose with no markers at all", id="plain-prose"),
    pytest.param("", id="empty-human-body"),
]


@pytest.mark.parametrize("body", RESERVED)
def test_exact_marker_spelling_in_human_content_fails_closed(body: str) -> None:
    """The reserved half of the policy."""
    with pytest.raises(ProtectedRegionError):
        merge_protected_regions(existing=_note(body), rendered=_render(), path=PATH)


@pytest.mark.parametrize("body", RESERVED)
def test_refusal_leaves_the_note_bytes_untouched(body: str) -> None:
    """F3 is availability, not data loss.

    The refusal must not be a partial write, and the caller's text must come
    back through unmodified -- an operator who hits this keeps their note.
    """
    existing = _note(body)
    before = existing
    with pytest.raises(ProtectedRegionError):
        merge_protected_regions(existing=existing, rendered=_render(), path=PATH)
    assert existing == before


@pytest.mark.parametrize("body", ORDINARY)
def test_near_miss_and_bare_tokens_remain_ordinary_text(body: str) -> None:
    """The permissive half -- previously unasserted, and the half a careless
    "just reserve anything that looks like a marker" change would break.

    The count is over the *full comment string*, so a bare
    ``atlas:generated:start`` is deliberately unaffected.
    """
    merged = merge_protected_regions(
        existing=_note(body), rendered=_render(), path=PATH
    )
    assert body in merged, "human content must survive verbatim"
    assert "new generated body" in merged


def test_nested_human_structure_still_works_alongside_the_rule() -> None:
    """Reserved-everywhere must not disturb F2's nested-region semantics.

    This is the property the rejected 'opaque HUMAN payload' option would
    have destroyed: an inner BEGIN HUMAN is *structure*, not prose.
    """
    existing = (
        f"{GENERATED_START}\nold\n{GENERATED_END}\n\n"
        "<!-- BEGIN HUMAN: outer -->\nOUTER\n"
        "<!-- BEGIN HUMAN: inner -->\nINNER\n<!-- END HUMAN: inner -->\n"
        "<!-- END HUMAN: outer -->\n"
    )
    rendered = (
        f"{GENERATED_START}\nnew\n{GENERATED_END}\n\n"
        "<!-- BEGIN HUMAN: outer -->\n\n"
        "<!-- BEGIN HUMAN: inner -->\n\n<!-- END HUMAN: inner -->\n"
        "<!-- END HUMAN: outer -->\n"
    )
    merged = merge_protected_regions(existing=existing, rendered=rendered, path=PATH)
    assert "OUTER" in merged and "INNER" in merged


def test_repeat_refresh_is_stable_for_ordinary_content() -> None:
    existing = _note("ordinary notes")
    rendered = _render()
    once = merge_protected_regions(existing=existing, rendered=rendered, path=PATH)
    twice = merge_protected_regions(existing=once, rendered=rendered, path=PATH)
    assert once == twice


def test_refusal_names_the_path_and_reports_observable_counts() -> None:
    """The diagnostic must carry facts, and must not assert a cause.

    ``start_count > 1`` has at least two causes -- an operator-authored
    reserved spelling, and genuinely malformed Atlas structure. The message
    is checked for the observable facts only; it must not claim which
    happened, because at this point the code cannot know.
    """
    with pytest.raises(ProtectedRegionError) as excinfo:
        merge_protected_regions(
            existing=_note(f"x {GENERATED_START} y"), rendered=_render(), path=PATH
        )
    message = str(excinfo.value)
    assert PATH in message
    assert "start=2" in message and "expected=1" in message
    assert "note_unchanged=yes" in message
    lowered = message.lower()
    assert "you " not in lowered, "must not attribute the cause to the operator"
