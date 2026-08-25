"""AS-CODER-ALPHA-OBS-READ-001 — vault-scoped observability REPORT READ."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.cli import EXIT_ERROR, EXIT_OK, build_parser, main
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.obs_live import build_live_observability_receipt
from project_atlas.web_api.obs import (
    PACKAGE_ID,
    TOOL_ID,
    TRUTH_BOUNDARY,
    WebObsError,
    read_obs,
    render_obs_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebObsError, match="obs-vault-missing"):
        read_obs(tmp_path / "absent")


def test_empty_vault_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_obs(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["tool_id"] == TOOL_ID
    assert view["status"] == "UNKNOWN"
    assert view["healthy"] is False
    assert view["empty"] is True
    assert view["reason_code"] == "EMPTY_RECEIPT"
    assert view["receipt_rollup"] == "unknown"
    assert view["honesty"]["obs_is_authority"] is False
    assert view["honesty"]["live_receipt_is_certification"] is False
    assert view["honesty"]["empty_is_healthy"] is False
    assert view["honesty"]["unknown_is_healthy"] is False
    assert view["honesty"]["mcp_is_authority"] is False
    assert view["honesty"]["write_applied"] is False
    assert view["truth_boundary"] == TRUTH_BOUNDARY
    text = render_obs_text(view)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "WRITE_APPLIED=false" in text


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    view = read_obs(vault)
    assert view["honesty"]["write_applied"] is False
    assert _snapshot(vault) == before
    assert not (vault / "generated" / "ops" / "obs").exists()


def test_present_markers_stay_unknown_not_certification(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "generated" / "ops" / "chatgpt").mkdir(parents=True)
    (vault / "generated" / "ops" / "perf").mkdir(parents=True)
    view = read_obs(vault)
    assert view["status"] == "UNKNOWN"
    assert view["healthy"] is False
    assert view["empty"] is False
    assert view["reason_code"] == "LIVE_RECEIPT_UNKNOWN"
    assert view["optional_marker_count"] == 2
    assert view["receipt"]["surfaces"]["chatgpt_bridge"] is True
    assert view["receipt"]["surfaces"]["perf_baselines"] is True
    assert view["honesty"]["live_receipt_is_certification"] is False
    assert view["honesty"]["unknown_is_healthy"] is False
    assert not (vault / "generated" / "ops" / "obs").exists()


def test_write_false_does_not_persist_source_receipt(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    receipt = build_live_observability_receipt(
        vault, receipt_id="obs-read", write=False
    )
    assert receipt["rollup"] == "unknown"
    assert not (vault / "generated" / "ops" / "obs").exists()


def test_default_source_builder_still_persists(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    receipt = build_live_observability_receipt(vault, receipt_id="api-obs")
    written = vault / "generated" / "ops" / "obs" / "api-obs-live.json"
    assert written.is_file()
    assert receipt["receipt_id"] == "api-obs"


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "generated" / "ops" / "ask").mkdir(parents=True)
    first = read_obs(vault)
    second = read_obs(vault)
    assert first == second


def test_vault_bind_does_not_import_sibling_markers(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "generated" / "ops" / "scheduler").mkdir(parents=True)
    left_view = read_obs(left)
    right_view = read_obs(right)
    assert left_view["empty"] is False
    assert right_view["empty"] is True
    assert left_view["receipt"]["surfaces"]["scheduler"] is True
    assert right_view["receipt"]["surfaces"]["scheduler"] is False


def test_appservice_obs(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.obs()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    assert view["honesty"]["write_applied"] is False
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_empty_vault(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["ops", "obs", "--vault", str(vault), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["package_id"] == PACKAGE_ID
    assert payload["status"] == "UNKNOWN"
    assert payload["healthy"] is False
    assert payload["honesty"]["write_applied"] is False


def test_cli_text_and_no_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["ops", "obs", "--vault", str(vault)]) == EXIT_OK
    text = capsys.readouterr().out
    assert "atlas ops obs [UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["ops", "obs", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_ops_obs_command_is_free_and_ascii(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "ops" in help_text
    assert all(ord(char) < 128 for char in help_text)
    read_args = parser.parse_args(["ops", "obs", "--vault", "/tmp/vault"])
    assert read_args.ops_command == "obs"
    report_args = parser.parse_args(["ops", "report", "--vault", "/tmp/vault"])
    assert report_args.ops_command == "report"
    health_args = parser.parse_args(["ops", "health", "--vault", "/tmp/vault"])
    assert health_args.ops_command == "health"
    with pytest.raises(SystemExit) as exc:
        main(["obs", "show", "--vault", "/tmp/vault"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as help_exc:
        main(["ops", "obs", "--help"])
    assert help_exc.value.code == 0
    obs_help = capsys.readouterr().out
    assert all(ord(char) < 128 for char in obs_help)
    assert "atlas ops obs --vault" in obs_help


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.obs.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.obs.write" not in listing["tools"]


def test_mcp_empty_vault_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    report = invoke_mcp_tool(vault, "atlas.obs.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["healthy"] is False
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["write_applied"] is False
    assert _snapshot(vault) == before


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.obs.read", "args": {"write": True}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.obs.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.obs.read", operator=bare)


def test_d149_surfaces_untouched() -> None:
    root = Path(__file__).resolve().parents[2]
    authentic = (
        root / "src/project_atlas/orchestration/autonomy/authentic_estate.py"
    ).read_text(encoding="utf-8")
    reconciler = (
        root / "src/project_atlas/orchestration/sdk/mission_reconciler.py"
    ).read_text(encoding="utf-8")
    assert "AS-CODER-ALPHA-OBS-READ-001" not in authentic
    assert "AS-CODER-ALPHA-OBS-READ-001" not in reconciler
    assert "atlas.obs.read" not in authentic
    assert "atlas.obs.read" not in reconciler
