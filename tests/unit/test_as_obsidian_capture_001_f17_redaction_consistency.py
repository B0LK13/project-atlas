"""AS-OBSIDIAN-CAPTURE-001 F17 -- redaction must be a property of the field.

`render_relationships_markdown` redacted `relationship_id` in its table and
then echoed the same field verbatim two lines below, in the Source linkage
block. That is worse than not redacting at all: a reviewer reading the table
sees the control working, and the raw value is on the page regardless.

What these tests pin is *consistency* -- that a field redacted in one part of
the note is redacted in every part of it. They deliberately do **not** claim
`_redact_text` is a strong redactor. It matches on `=`-delimited needles and
misses plenty (`tokenSUPERSECRET` with no `=`, `aws_secret_access_key AKIA`).
Routing more fields through a weak function inherits its weakness, and a test
that implied otherwise would be the same kind of reassuring-but-false signal
this defect already produced once.
"""

from __future__ import annotations

from typing import Any

import pytest

from project_atlas.graph_projections import render_relationships_markdown

SECRET = "token=SUPERSECRET-abc123"
REDACTED = "redacted-sensitive"


def _record(**over: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "project_id": "p",
        "relationship_id": "rel-1",
        "relationship_type": "depends_on",
        "source_entity_id": "a",
        "target_entity_id": "b",
        "link_quality": "verified",
        "relationship_fingerprint": "f" * 64,
        "provenance": {"graphify_artifact_refs": [{"relative_path": "ok.md", "sha256": "d" * 64}]},
    }
    record.update(over)
    return record


def test_f17_relationship_id_is_not_echoed_raw_after_being_redacted() -> None:
    """The defect itself: redacted at `graph_projections.py:355`, raw below it."""
    out = render_relationships_markdown([_record(relationship_id=SECRET)], project_id="p")
    assert SECRET not in out, "the field redacted in the table is verbatim in the note"
    # Both sites must render the placeholder -- one alone was the bug.
    assert out.count(REDACTED) >= 2


def test_f17_artifact_relative_path_is_redacted() -> None:
    """The second bypassing field in the same block."""
    refs = [{"relative_path": SECRET, "sha256": "d" * 64}]
    out = render_relationships_markdown(
        [_record(provenance={"graphify_artifact_refs": refs})], project_id="p"
    )
    assert SECRET not in out


def test_f17_a_secret_shaped_sha256_does_not_leak_through_the_slice() -> None:
    """`sha256` is not validated as hex here, so the 16-char slice is not safe.

    Slicing bounds how much escapes; it does not make what escapes harmless.
    This is why the digest leg is redacted rather than trusted to its length.
    """
    refs = [{"relative_path": "ok.md", "sha256": "token=SUPERSECRETVALUE"}]
    out = render_relationships_markdown(
        [_record(provenance={"graphify_artifact_refs": refs})], project_id="p"
    )
    assert "token=SUPERSEC" not in out


@pytest.mark.parametrize(
    "field",
    ["relationship_id", "relationship_type", "source_entity_id", "target_entity_id"],
)
def test_f17_every_rendered_identifier_field_is_redacted_somewhere(field: str) -> None:
    """A sweep, so a NEW raw render site fails rather than passing unnoticed.

    The original defect was one field rendered at two sites with two different
    rules. Checking the whole note for the value catches that shape regardless
    of which block a future edit adds.
    """
    out = render_relationships_markdown([_record(**{field: SECRET})], project_id="p")
    assert SECRET not in out, f"{field} reaches the note verbatim"


def test_f17_the_sweep_can_actually_fail() -> None:
    """Non-vacuity: the corpus value really is one `_redact_text` acts on.

    If `SECRET` were not secret-shaped, every assertion above would pass for
    the wrong reason and keep passing after a regression.
    """
    from project_atlas.graph_projections import _redact_text

    assert _redact_text(SECRET) == REDACTED, "the fixture value is not redactable"
    assert _redact_text("harmless") == "harmless", "_redact_text redacts everything"
