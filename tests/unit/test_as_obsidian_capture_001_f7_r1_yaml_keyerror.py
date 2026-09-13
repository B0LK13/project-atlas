"""AS-OBSIDIAN-CAPTURE-001-F7-R1 — contain yaml.safe_load KeyError.

F7 sealed a BOM-ownership residual and recorded, rather than fixed, that
``yaml.safe_load`` raises a bare ``KeyError`` (not ``yaml.YAMLError``) for a
malformed explicit bool tag. ``_existing_capture_id`` caught only
``yaml.YAMLError``, so the public ``retry()`` API escaped with a traceback
instead of a structured ``OBSIDIAN_NOTE_CONFLICT``.

Outcome on main was already fail-closed (note bytes unchanged). The defect is
the **mechanism**: a constructor ``KeyError`` bypasses ``ObsidianNoteError``
and ``_render_stage``'s ``(CaptureError, ObsidianNoteError, OSError, ValueError)``
guard.

This package does **not** widen acceptance. The same shape is still refused
as unmanaged; only the exception class is contained.

Reproducer (F7 evidence): ``---\\natlas: !!bool nope\\n---\\nbody\\n``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.capture_sources import build_capture_request
from project_atlas.obsidian_capture import capture, retry
from project_atlas.obsidian_capture_note import _existing_capture_id

BOM = "\ufeff"

# F7 residual register. Must not raise KeyError; must not become owned.
MALFORMED_BOOL_TAG = "---\natlas: !!bool nope\n---\nbody\n"


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "projects" / "harbor-api").mkdir(parents=True)
    (root / "generated").mkdir(parents=True)
    return root


def _note(vault: Path, result: dict) -> Path:
    output = result["outputs"][0]
    return Path(str(output["vault_root"])) / str(output["relative_path"])


def test_f7_r1_probe_returns_none_instead_of_keyerror() -> None:
    """Unit-level: the ownership probe itself, without the capture machinery."""
    assert _existing_capture_id(MALFORMED_BOOL_TAG) is None
    assert _existing_capture_id(BOM + MALFORMED_BOOL_TAG) is None
    assert _existing_capture_id(MALFORMED_BOOL_TAG.replace("\n", "\r\n")) is None


def test_f7_r1_probe_still_recognises_well_formed_frontmatter() -> None:
    frontmatter = "---\natlas:\n  managed: true\n  capture_id: rcap-abc\n---\nbody\n"
    assert _existing_capture_id(frontmatter) == "rcap-abc"


@pytest.mark.parametrize(
    "label,mutate",
    [
        ("bool-tag", lambda _t: MALFORMED_BOOL_TAG),
        ("bool-tag-bom", lambda _t: BOM + MALFORMED_BOOL_TAG),
        ("bool-tag-crlf", lambda _t: MALFORMED_BOOL_TAG.replace("\n", "\r\n")),
    ],
)
def test_f7_r1_retry_returns_structured_conflict(
    label: str, mutate, vault: Path
) -> None:
    result = capture(vault, build_capture_request(content=f"f7-r1 {label}"))
    note = _note(vault, result)
    note.write_bytes(mutate(note.read_bytes().decode("utf-8")).encode("utf-8"))
    mutated = note.read_bytes()

    outcome = retry(vault, result["capture_id"])

    assert outcome["status"] != "ok", (
        f"{label}: retry accepted a constructor-tag corrupt note"
    )
    codes = {e.get("code") for e in (outcome.get("errors") or [])}
    assert "OBSIDIAN_NOTE_CONFLICT" in codes, (
        f"{label}: refused for the wrong reason: {codes}"
    )
    assert note.read_bytes() == mutated, f"{label}: the refused note was modified"


def test_f7_r1_retry_does_not_raise_keyerror(vault: Path) -> None:
    """The public API must return a result dict, never leak KeyError."""
    result = capture(vault, build_capture_request(content="f7-r1 no raise"))
    note = _note(vault, result)
    note.write_text(MALFORMED_BOOL_TAG, encoding="utf-8")

    outcome = retry(vault, result["capture_id"])

    assert isinstance(outcome, dict)
    assert outcome.get("status") != "ok"
