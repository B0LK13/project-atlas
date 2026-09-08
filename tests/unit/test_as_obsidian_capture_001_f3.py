"""AS-OBSIDIAN-CAPTURE-001-F3 — Atlas marker spellings are reserved everywhere.

Owner policy: the exact Atlas structural marker spellings are reserved syntax
wherever they appear, *including* inside a HUMAN protected region. A note
carrying one is therefore a structural collision, not opaque prose, and the
refresh fails closed with the note left byte-identical.

These tests pin two things. The safety behaviour, which already held before
this work package and must not regress; and the diagnostic, which is what F3
actually changes -- the refusal now reports the observable marker counts and
whether a reserved spelling sits inside a HUMAN region, without claiming who
wrote it. See ``docs/evidence/AS-OBSIDIAN-CAPTURE-001-F3-RESERVED-MARKER-CLOSURE.md``.

Truth boundary: a refusal is availability, not data loss. Raw HUMAN bytes are
never rewritten -- no escaping, no normalisation, no zero-width insertion.
"""

from __future__ import annotations

import time

import pytest

from project_atlas.protected_regions import (
    GENERATED_END,
    GENERATED_START,
    ProtectedRegionError,
    merge_protected_regions,
)


def _note(human_body: str) -> str:
    return (
        f"{GENERATED_START}\ngenerated body\n{GENERATED_END}\n\n"
        f"<!-- BEGIN HUMAN: notes -->\n{human_body}<!-- END HUMAN: notes -->\n"
    )


_FRESH = _note("")


def _merge(existing: str) -> str:
    return merge_protected_regions(existing=existing, rendered=_FRESH, path="note.md")


# --- reserved spellings inside HUMAN content fail closed -----------------------

RESERVED = {
    "generated-start": f"I document the {GENERATED_START} marker here.\n",
    "generated-end": f"I document the {GENERATED_END} marker here.\n",
    # Load-bearing: a *balanced* forged pair must not become valid structure by
    # accident. Counting alone would see two begins and two ends and could call
    # that balanced; it is refused because one generated span is the maximum.
    "balanced-forged-pair": f"Everything from {GENERATED_START} to {GENERATED_END}.\n",
    "human-begin": "See <!-- BEGIN HUMAN: x --> for the syntax.\n",
    "human-end": "See <!-- END HUMAN: x --> for the syntax.\n",
}


@pytest.mark.parametrize("label", sorted(RESERVED))
def test_f3_reserved_spelling_in_human_fails_closed(label: str) -> None:
    existing = _note(RESERVED[label])
    with pytest.raises(ProtectedRegionError):
        _merge(existing)


@pytest.mark.parametrize("label", sorted(RESERVED))
def test_f3_refusal_leaves_the_note_byte_identical(label: str) -> None:
    """No escaping, no normalisation, no zero-width rewriting of HUMAN bytes."""
    body = RESERVED[label]
    existing = _note(body)
    before = existing.encode("utf-8")
    with pytest.raises(ProtectedRegionError):
        _merge(existing)
    assert existing.encode("utf-8") == before
    # The author's exact bytes are still there, unescaped and unmutated.
    assert body in existing
    assert "​" not in existing
    assert "&lt;!--" not in existing


def test_f3_repeated_refusal_is_stable() -> None:
    """Refusing twice yields the same class and still no mutation."""
    existing = _note(RESERVED["generated-start"])
    before = existing
    classes = []
    for _ in range(2):
        with pytest.raises(ProtectedRegionError) as caught:
            _merge(existing)
        classes.append(str(caught.value).split(":")[0])
    assert classes[0] == classes[1]
    assert existing == before


# --- near misses stay ordinary HUMAN prose ------------------------------------

NEAR_MISS = {
    "bare-token-no-comment": "The token atlas:generated:start is inert prose.\n",
    "extra-inner-spacing": "<!--  atlas:generated:start  -->\n",
    "suffix-variant": "<!-- atlas:generated:startx -->\n",
    "uppercase-variant": "<!-- ATLAS:GENERATED:START -->\n",
    "partial-token": "<!-- atlas:generated: -->\n",
    "ordinary-html-comment": "<!-- just an ordinary note -->\n",
    "human-marker-without-name": "<!-- BEGIN HUMAN: -->\n",
    # #716's split-token near miss. Recorded as an open residual in the F1-F4
    # register ("pinned by no assertion") and pinned here. A whitespace-tolerant
    # marker matcher would start REFUSING these, turning ordinary prose into a
    # permanent refresh failure, and nothing would have caught it.
    "split-token-inside-start": "<!-- atlas:generated:sta rt -->\n",
    "split-token-inside-end": "<!-- atlas:generated:e nd -->\n",
    "split-token-before-colon": "<!-- atlas:generated :start -->\n",
    "split-token-across-newline": "<!-- atlas:generated:sta\nrt -->\n",
}


@pytest.mark.parametrize("label", sorted(NEAR_MISS))
def test_f3_near_miss_is_ordinary_text_and_survives(label: str) -> None:
    """Only the exact spelling is reserved; near misses are preserved prose."""
    body = NEAR_MISS[label]
    merged = _merge(_note(body))
    assert body.strip() in merged


def test_f3_near_miss_repeat_refresh_is_stable() -> None:
    body = NEAR_MISS["bare-token-no-comment"]
    first = _merge(_note(body))
    assert _merge(first) == first


# --- byte fidelity across line endings and unicode ----------------------------


@pytest.mark.parametrize(
    ("label", "body"),
    [
        ("crlf", "line one\r\nline two\r\n"),
        ("unicode", "naïve café — ✅ 日本語 🎉\n"),
        ("leading-trailing-space", "   padded   \n"),
        ("markdown", "- item\n\n> quote\n\n```\ncode\n```\n"),
        ("html-like-prose", "<div>not a marker</div>\n"),
        ("no-trailing-newline", "no trailing newline"),
    ],
)
def test_f3_accepted_content_keeps_its_bytes(label: str, body: str) -> None:
    merged = _merge(_note(body))
    assert body in merged, f"{label}: human bytes were altered"


def test_f3_crlf_note_with_reserved_marker_still_fails_closed_unchanged() -> None:
    body = f"line one\r\n{GENERATED_START}\r\nline two\r\n"
    existing = _note(body)
    before = existing.encode("utf-8")
    with pytest.raises(ProtectedRegionError):
        _merge(existing)
    assert existing.encode("utf-8") == before


# --- the diagnostic: observable facts, no authorship claim --------------------


def test_f3_diagnostic_reports_observable_marker_counts() -> None:
    existing = _note(RESERVED["generated-start"])
    with pytest.raises(ProtectedRegionError) as caught:
        _merge(existing)
    message = str(caught.value)
    assert message.startswith("malformed-generated-markers:"), message
    assert "begin=2" in message and "end=1" in message and "expected=1" in message
    assert "no-write" in message


def test_f3_diagnostic_names_the_reserved_marker_containment_when_observable() -> None:
    """A reserved spelling inside a HUMAN span is an observable fact; say so."""
    existing = _note(RESERVED["generated-start"])
    with pytest.raises(ProtectedRegionError) as caught:
        _merge(existing)
    assert "reserved-marker-in-human-region" in str(caught.value)


def test_f3_diagnostic_makes_no_authorship_claim() -> None:
    """Causal honesty: the same shape can arise without any operator action."""
    existing = _note(RESERVED["generated-start"])
    with pytest.raises(ProtectedRegionError) as caught:
        _merge(existing)
    message = str(caught.value).lower()
    for forbidden in ("you typed", "you wrote", "you added", "authored by"):
        assert forbidden not in message


def test_f3_structural_corruption_outside_human_is_not_blamed_on_a_region() -> None:
    """A duplicated generated marker outside any HUMAN region must not be
    reported as a reserved-marker-in-human-region collision."""
    existing = (
        f"{GENERATED_START}\nbody\n{GENERATED_END}\n{GENERATED_START}\n\n"
        "<!-- BEGIN HUMAN: notes -->\nplain prose\n<!-- END HUMAN: notes -->\n"
    )
    with pytest.raises(ProtectedRegionError) as caught:
        _merge(existing)
    message = str(caught.value)
    assert "reserved-marker-in-human-region" not in message
    assert "begin=2" in message


def test_f3_end_before_begin_reports_its_own_reason() -> None:
    existing = (
        f"{GENERATED_END}\nbody\n{GENERATED_START}\n\n"
        "<!-- BEGIN HUMAN: notes -->\nplain prose\n<!-- END HUMAN: notes -->\n"
    )
    with pytest.raises(ProtectedRegionError) as caught:
        _merge(existing)
    assert "end-before-begin" in str(caught.value)


# --- containment must agree with the canonical grammar, or stay silent -------
#
# The diagnostic's containment fact is only honest if it uses the same marker
# grammar and the same pairing rule as the canonical parser. A permissive
# variant would report a reserved marker as sitting "in a HUMAN region" that
# the canonical parser does not recognise as a region at all.


def _generated_collision_message(document: str) -> str:
    with pytest.raises(ProtectedRegionError) as caught:
        merge_protected_regions(existing=document, rendered=_FRESH, path="n.md")
    return str(caught.value)


def test_f3_unnamed_marker_pair_is_not_a_human_region_for_containment() -> None:
    """``<!-- BEGIN HUMAN: -->`` has no name, so canonically it is not a region."""
    document = (
        f"{GENERATED_START}\ngenerated body\n{GENERATED_END}\n"
        f"<!-- BEGIN HUMAN: -->\nprose {GENERATED_START} prose\n<!-- END HUMAN: -->\n"
    )
    message = _generated_collision_message(document)
    assert "begin=2" in message
    assert "reserved-marker-in-human-region" not in message


def test_f3_crossed_human_structure_is_not_determinable_containment() -> None:
    """Crossed markers do not pair, so containment cannot be asserted."""
    document = (
        f"{GENERATED_START}\ngenerated body\n{GENERATED_END}\n"
        "<!-- BEGIN HUMAN: a -->\n<!-- BEGIN HUMAN: b -->\n"
        f"{GENERATED_START}\n"
        "<!-- END HUMAN: a -->\n<!-- END HUMAN: b -->\n"
    )
    assert "reserved-marker-in-human-region" not in _generated_collision_message(document)


def test_f3_orphan_end_marker_is_not_determinable_containment() -> None:
    document = (
        f"{GENERATED_START}\ngenerated body\n{GENERATED_END}\n"
        f"<!-- END HUMAN: a -->\n{GENERATED_START}\n"
    )
    assert "reserved-marker-in-human-region" not in _generated_collision_message(document)


def test_f3_unclosed_begin_is_not_determinable_containment() -> None:
    document = (
        f"{GENERATED_START}\ngenerated body\n{GENERATED_END}\n"
        f"<!-- BEGIN HUMAN: a -->\n{GENERATED_START}\n"
    )
    assert "reserved-marker-in-human-region" not in _generated_collision_message(document)


def test_f3_properly_named_region_still_reports_containment() -> None:
    """The tightening must not silence the true positive."""
    document = (
        f"{GENERATED_START}\ngenerated body\n{GENERATED_END}\n"
        f"<!-- BEGIN HUMAN: notes -->\nprose {GENERATED_START} prose\n"
        "<!-- END HUMAN: notes -->\n"
    )
    assert "reserved-marker-in-human-region" in _generated_collision_message(document)


def test_f3_refusal_diagnostic_stays_linear_on_a_large_malformed_note() -> None:
    """Formatting a refusal must not become the expensive part of refusing.

    The containment check walks marker positions and region spans together
    rather than comparing every marker against every span. Comparing them
    pairwise was quadratic on exactly the input that reaches this path -- a
    large malformed note with many markers and many sibling regions -- where it
    cost seconds purely to build an error message. The bound here is generous;
    it is chosen to catch a return to quadratic behaviour, not to police
    micro-performance.
    """
    count = 20_000
    regions = "".join(
        f"<!-- BEGIN HUMAN: r{index} -->\nx\n<!-- END HUMAN: r{index} -->\n"
        for index in range(count)
    )
    document = f"{GENERATED_START}\n" * count + f"{GENERATED_END}\n" + regions

    started = time.perf_counter()
    with pytest.raises(ProtectedRegionError) as caught:
        merge_protected_regions(existing=document, rendered=_FRESH, path="big.md")
    elapsed = time.perf_counter() - started

    assert f"begin={count}" in str(caught.value)
    assert elapsed < 5.0, f"refusal diagnostic took {elapsed:.1f}s; quadratic scan is back"
