"""AS-CODER-ALPHA-HANDOFF-READ-001 — vault-scoped handoff REPORT READ."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.mcp_server import invoke_mcp_tool
from project_atlas.web_api.handoff_read import (
    PACKAGE_ID,
    WebHandoffReadError,
    read_handoff_view,
    render_handoff_text,
    show_handoff_view,
)


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


def _write_pack(vault: Path, handoff_id: str, project_id: str = "harbor-api") -> None:
    directory = vault / "generated" / "ops" / "handoffs"
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "handoff_id": handoff_id,
        "project_id": project_id,
        "note": "persisted pack",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
    }
    (directory / f"{handoff_id}.json").write_text(
        json.dumps(payload) + "\n", encoding="utf-8"
    )
    (directory / "latest.json").write_text(
        json.dumps({"handoff_id": handoff_id, "path": f"generated/ops/handoffs/{handoff_id}.json"})
        + "\n",
        encoding="utf-8",
    )


def test_empty_vault_is_empty_not_healthy(tmp_path: Path) -> None:
    report = read_handoff_view(_vault(tmp_path))
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "EMPTY"
    assert report["available"] is False
    assert report["honesty"]["write_applied"] is False
    assert report["honesty"]["resume_invoked"] is False
    assert report["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    text = render_handoff_text(report)
    assert "EMPTY != HEALTHY" in text
    assert all(ord(char) < 128 for char in text)


def test_present_pack_is_not_authority(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_pack(vault, "h1")
    report = read_handoff_view(vault)
    assert report["status"] == "PRESENT"
    assert report["view"]["artifact_count"] == 1
    assert report["view"]["create_invoked"] is False
    assert report["view"]["resume_invoked"] is False
    shown = show_handoff_view(vault, handoff_id="h1")
    assert shown["view"]["selected"]["handoff_id"] == "h1"
    assert shown["status"] == "PRESENT"


def test_unknown_id_stays_unknown(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_pack(vault, "h1")
    report = show_handoff_view(vault, handoff_id="missing")
    assert report["status"] == "UNKNOWN"
    assert report["reason_code"] == "UNKNOWN_HANDOFF_ID"
    assert report["available"] is False


def test_malformed_mixed_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_pack(vault, "h1")
    (vault / "generated" / "ops" / "handoffs" / "bad.json").write_text("{nope", encoding="utf-8")
    report = read_handoff_view(vault)
    assert report["status"] == "UNKNOWN"
    assert report["view"]["malformed_count"] == 1
    assert report["available"] is False


def test_id_collision_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_pack(vault, "h1")
    other = vault / "generated" / "ops" / "handoffs" / "h1-dup.json"
    other.write_text(
        json.dumps({"handoff_id": "h1", "project_id": "harbor-api", "note": "altered"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(WebHandoffReadError, match="handoff-read-id-collision"):
        read_handoff_view(vault)


def test_merge_and_pilot_invention_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    directory = vault / "generated" / "ops" / "handoffs"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "bad-merge.json").write_text(
        json.dumps({"handoff_id": "x", "MERGE_AUTHORIZATION": "GRANTED"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(WebHandoffReadError, match="merge-authority-invented"):
        read_handoff_view(vault)
    (directory / "bad-merge.json").write_text(
        json.dumps({"handoff_id": "x", "authentic_pilot": True}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(WebHandoffReadError, match="authentic-pilot-invented"):
        read_handoff_view(vault)


def test_render_is_ascii_even_with_unicode_project(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_pack(vault, "h1", project_id="harbör-api")
    text = render_handoff_text(read_handoff_view(vault))
    assert all(ord(char) < 128 for char in text)
    assert "harb?r-api" in text


def test_symlink_pack_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_pack(vault, "h1")
    foreign = tmp_path / "foreign.json"
    foreign.write_text(json.dumps({"handoff_id": "leak", "project_id": "other"}) + "\n")
    link = vault / "generated" / "ops" / "handoffs" / "link.json"
    link.symlink_to(foreign)
    with pytest.raises(WebHandoffReadError, match="handoff-read-symlink-forbidden"):
        read_handoff_view(vault)


def test_unsafe_id_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebHandoffReadError, match="handoff-read-unsafe-id"):
        show_handoff_view(_vault(tmp_path), handoff_id="../secret")


def test_module_does_not_write_or_resume() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/handoff_read.py").read_text(encoding="utf-8")
    for name in (
        "from project_atlas.agent_handoff",
        "write_text(",
        "write_json_atomic",
        "from project_atlas.ingestion",
        "from project_atlas.atlas3",
    ):
        assert name not in source
    assert "never calls create_handoff" in source


def test_cli_report_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    assert main(["handoff-status", "report", "--vault", str(vault)]) == EXIT_OK
    rendered = capsys.readouterr().out
    assert "EMPTY" in rendered
    assert all(ord(char) < 128 for char in rendered)
    _write_pack(vault, "h1")
    assert main(["handoff-status", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PRESENT"
    assert main(["handoff-status", "show", "--vault", str(vault), "--handoff-id", "h1"]) == EXIT_OK
    shown = capsys.readouterr().out
    assert "PRESENT" in shown or "HANDOFF" in shown


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    try:
        code = main(["handoff-status", "--help"])
    except SystemExit as exc:
        code = int(exc.code or 0)
    assert code == 0
    help_text = capsys.readouterr().out
    assert "does not write" in help_text or "read-only" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_mcp_handoff_read_empty(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    report = invoke_mcp_tool(vault, "atlas.handoff.read")
    assert report["tool_id"] == "atlas.handoff.read"
    assert report["live_mcp_read"] is True
    payload = report["result"]
    assert payload["package_id"] == PACKAGE_ID
    assert payload["status"] == "EMPTY"
    assert payload["honesty"]["write_applied"] is False


def test_unknown_vault_is_operational_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    assert main(["handoff-status", "report", "--vault", str(missing)]) == EXIT_ERROR
