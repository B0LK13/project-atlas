"""AS-CODER-ALPHA-OPS-REPORT-READ-001 — vault-scoped ops-report REPORT READ."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.mcp_server import invoke_mcp_tool
from project_atlas.web_api.ops_report_read import (
    PACKAGE_ID,
    WebOpsReportReadError,
    read_ops_report_view,
    render_ops_report_text,
)


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


def _write_report(vault: Path, *, estate: str = "unknown") -> None:
    directory = vault / "generated" / "ops"
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "atlas.ops.report.v1",
        "rollup": {"estate": estate},
        "snapshot_status": "present",
        "signals": [],
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
    }
    (directory / "ops-report.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")
    (directory / "ops-report.md").write_text("# ops-report\n", encoding="utf-8")


def test_empty_vault_is_empty_not_healthy(tmp_path: Path) -> None:
    report = read_ops_report_view(_vault(tmp_path))
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "EMPTY"
    assert report["available"] is False
    assert report["honesty"]["write_applied"] is False
    assert report["honesty"]["emit_invoked"] is False
    assert report["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    text = render_ops_report_text(report)
    assert "EMPTY != HEALTHY" in text
    assert all(ord(char) < 128 for char in text)


def test_present_report_is_not_authority(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_report(vault, estate="degraded")
    report = read_ops_report_view(vault)
    assert report["status"] == "PRESENT"
    assert report["view"]["json_present"] is True
    assert report["view"]["emit_invoked"] is False
    assert report["view"]["record"]["rollup"]["estate"] == "degraded"
    text = render_ops_report_text(report)
    assert "degraded" in text


def test_malformed_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    path = vault / "generated" / "ops" / "ops-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{nope", encoding="utf-8")
    report = read_ops_report_view(vault)
    assert report["status"] == "UNKNOWN"
    assert report["view"]["malformed_count"] == 1
    assert report["available"] is False


def test_merge_and_pilot_invention_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    directory = vault / "generated" / "ops"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "ops-report.json").write_text(
        json.dumps({"MERGE_AUTHORIZATION": "GRANTED"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(WebOpsReportReadError, match="merge-authority-invented"):
        read_ops_report_view(vault)
    (directory / "ops-report.json").write_text(
        json.dumps({"authentic_pilot": True}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(WebOpsReportReadError, match="authentic-pilot-invented"):
        read_ops_report_view(vault)


def test_render_is_ascii_even_with_unicode_rollup(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_report(vault, estate="degradéd")
    text = render_ops_report_text(read_ops_report_view(vault))
    assert all(ord(char) < 128 for char in text)
    assert "degrad?d" in text


def test_symlink_report_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    foreign = tmp_path / "foreign.json"
    foreign.write_text(json.dumps({"rollup": {"estate": "leak"}}) + "\n", encoding="utf-8")
    directory = vault / "generated" / "ops"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "ops-report.json").symlink_to(foreign)
    with pytest.raises(WebOpsReportReadError, match="ops-report-read-symlink-forbidden"):
        read_ops_report_view(vault)


def test_module_does_not_write_or_emit() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/ops_report_read.py").read_text(encoding="utf-8")
    for name in (
        "from project_atlas.ops_report",
        "emit_ops_report(",
        "write_text(",
        "write_json_atomic",
        "from project_atlas.ingestion",
        "from project_atlas.atlas3",
        "atlas.query.read",
    ):
        assert name not in source


def test_cli_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    assert main(["ops-report-status", "--vault", str(vault)]) == EXIT_OK
    rendered = capsys.readouterr().out
    assert "EMPTY" in rendered
    assert all(ord(char) < 128 for char in rendered)
    _write_report(vault)
    assert main(["ops-report-status", "--vault", str(vault), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PRESENT"


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    try:
        code = main(["ops-report-status", "--help"])
    except SystemExit as exc:
        code = int(exc.code or 0)
    assert code == 0
    help_text = capsys.readouterr().out
    assert "never writes" in help_text or "read-only" in help_text or "OPS REPORT" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_mcp_ops_report_read_empty(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    report = invoke_mcp_tool(vault, "atlas.ops.report.read")
    assert report["tool_id"] == "atlas.ops.report.read"
    assert report["live_mcp_read"] is True
    payload = report["result"]
    assert payload["package_id"] == PACKAGE_ID
    assert payload["status"] == "EMPTY"
    assert payload["honesty"]["write_applied"] is False


def test_unknown_vault_is_operational_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    assert main(["ops-report-status", "--vault", str(missing)]) == EXIT_ERROR
