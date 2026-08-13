"""D-042 / AS-CODER-ALPHA-CAPTURE-002 conversational capture coverage."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.cli import EXIT_OK, main
from project_atlas.connect import connect_project
from project_atlas.session_capture import (
    PACKAGE_CONVERSATIONAL,
    capture_context_export,
    capture_conversation,
    list_captures,
    render_captures_markdown,
)


def _seed(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "# Conv Capture\n\nPurpose: conversational memory.\n\n## Stack\n\nPython.\n",
        encoding="utf-8",
    )
    return root


def test_capture_conversation_plane_and_truth_boundary(tmp_path: Path) -> None:
    project = _seed(tmp_path / "conv-proj")
    vault = Path(connect_project(project)["vault"])
    report = capture_conversation(
        vault,
        "conv-proj",
        summary="Discussed governing decisions",
        turns=[
            {"role": "user", "text": "Which decisions govern current work?"},
            {"role": "assistant", "text": "ACTIVE_GOVERNING ADRs only."},
        ],
        source="conversational",
    )
    assert report["status"] == "ok"
    assert report["package"] == PACKAGE_CONVERSATIONAL
    assert report["plane"] == "conversational"
    assert report["turn_count"] == 2
    payload = json.loads((vault / report["path"]).read_text(encoding="utf-8"))
    assert payload["honesty"]["conversational_sole_certifier"] is False
    assert payload["honesty"]["lens_is_authority"] is False
    assert "≠ AUTHORITY" in payload["truth_boundary"]
    assert payload["authority"]["level"] == "ops-receipt"
    listed = list_captures(vault, project_id="conv-proj")
    assert listed[0]["plane"] == "conversational"
    md = "\n".join(render_captures_markdown(listed))
    assert "conversation/conversational" in md
    assert "≠ authority" in md


def test_context_export_default_conversational_capture(tmp_path: Path) -> None:
    project = _seed(tmp_path / "ctx-conv")
    vault = Path(connect_project(project)["vault"])
    assert (
        main(
            [
                "context",
                "--vault",
                str(vault),
                "--project",
                "ctx-conv",
                "--no-refresh",
            ]
        )
        == EXIT_OK
    )
    captures = list_captures(vault, project_id="ctx-conv")
    assert captures
    assert captures[0]["kind"] == "conversation"
    assert captures[0]["source"] == "context-export"

    before = len(captures)
    assert (
        main(
            [
                "context",
                "--vault",
                str(vault),
                "--project",
                "ctx-conv",
                "--no-refresh",
                "--no-capture",
            ]
        )
        == EXIT_OK
    )
    assert len(list_captures(vault, project_id="ctx-conv")) == before


def test_cli_capture_conversation_and_secret_redaction(tmp_path: Path) -> None:
    project = _seed(tmp_path / "cli-conv")
    vault = Path(connect_project(project)["vault"])
    secret_turn = "user:Bearer FAKESECRET_u3v4w5x6y7z8a9b0c1d2"
    assert (
        main(
            [
                "capture",
                "conversation",
                "--vault",
                str(vault),
                "--project",
                "cli-conv",
                "--summary",
                "Sensitive dialogue",
                "--turn",
                secret_turn,
                "--json",
            ]
        )
        == EXIT_OK
    )
    captures = list_captures(vault, project_id="cli-conv")
    cap_path = (
        vault
        / "generated"
        / "ops"
        / "session-captures"
        / f"{captures[0]['capture_id']}.json"
    )
    payload = json.loads(cap_path.read_text(encoding="utf-8"))
    blob = json.dumps(payload)
    assert "AKIAIOSFODNN7EXAMPLE" not in blob
    assert payload["turn_count"] == 1


def test_capture_context_export_helper(tmp_path: Path) -> None:
    project = _seed(tmp_path / "helper-conv")
    vault = Path(connect_project(project)["vault"])
    report = capture_context_export(vault, "helper-conv", note="fresh coding session")
    assert report["source"] == "context-export"
    assert report["kind"] == "conversation"
