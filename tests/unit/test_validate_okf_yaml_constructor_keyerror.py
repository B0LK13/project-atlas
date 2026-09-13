"""Contain yaml.safe_load constructor KeyError in OKF concept frontmatter.

``atlas validate`` records invalid OKF concept notes as structured errors.
PyYAML ``!!bool nope`` raises a bare ``KeyError``, not ``yaml.YAMLError``.
On live main ``b87b4a22`` that escaped ``_validate_okf_concept_note`` and
aborted the rest of the vault scan.

This package does not widen acceptance: the note is still invalid. Does
not touch ``ingestion.py``. Sibling of #819 / #820 / #822 / #823.
"""

from __future__ import annotations

from pathlib import Path

from project_atlas.validation import _validate_okf_concept_note, validate

MALFORMED = "---\natlas: !!bool nope\n---\nbody\n"


def test_okf_concept_note_constructor_tag_is_structured_error(tmp_path: Path) -> None:
    note = tmp_path / "projects" / "fixture" / "concepts.md"
    note.parent.mkdir(parents=True)
    note.write_text(MALFORMED, encoding="utf-8")
    errors: list[str] = []
    _validate_okf_concept_note(tmp_path, note, errors)
    assert errors
    assert errors[0].startswith("invalid OKF concept note")
    assert "nope" in errors[0]


def test_validate_constructor_tag_does_not_raise_keyerror(tmp_path: Path) -> None:
    for required in (
        "index.md",
        "projects/index.md",
        "sources/index.md",
        "01-portfolio/index.md",
    ):
        path = tmp_path / required
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n", encoding="utf-8")
    note = tmp_path / "projects" / "fixture" / "concepts.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(MALFORMED, encoding="utf-8")
    report = validate(tmp_path)
    assert report["ok"] is False
    assert any(
        item.startswith("invalid OKF concept note") and "nope" in item
        for item in report["errors"]
    )
