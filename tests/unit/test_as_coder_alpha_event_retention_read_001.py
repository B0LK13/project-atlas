"""AS-CODER-ALPHA-EVENT-RETENTION-READ-001 — vault-scoped REPORT READ lens."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.event_retention import (
    RetentionError,
    apply_event_retention,
    build_report,
    default_policy,
    read_report,
    write_report,
)
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.event_retention import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    WebEventRetentionError,
    read_event_retention,
    render_event_retention_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _write_unit(vault: Path, project: str, event: str) -> None:
    package = vault / "sources" / "agent-events" / project / event
    package.mkdir(parents=True, exist_ok=True)
    (package / "event.md").write_text(f"# {event}\n", encoding="utf-8")
    receipt_dir = vault / "receipts" / "agent-events" / project
    receipt_dir.mkdir(parents=True, exist_ok=True)
    (receipt_dir / f"{event}.yaml").write_text(
        f"receipt_id: {event}\nstatus: valid\nevent_id: {event}\n",
        encoding="utf-8",
    )


def _write_sample_report(
    vault: Path,
    *,
    status: Literal["applied", "dry-run", "no-op", "skipped-no-policy"] = "no-op",
    applied: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    report = build_report(
        policy=default_policy(max_packages=10, max_bytes=4096),
        units_before=0,
        bytes_before=0,
        kept=[],
        removed=[],
        deleted_paths=[],
        applied=applied,
        dry_run=dry_run,
        status=status,
    )
    write_report(vault, report)
    return report


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebEventRetentionError, match="event-retention-vault-missing"):
        read_event_retention(tmp_path / "absent")


def test_missing_report_is_unknown_not_applied(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert read_report(vault) is None
    view = read_event_retention(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["report_present"] is False
    assert view["report"] is None
    assert view["reason_code"] == "REPORT_ABSENT"
    assert view["honesty"]["missing_is_applied"] is False
    assert view["honesty"]["report_is_authority"] is False
    assert view["honesty"]["retention_report_is_apply"] is False
    assert view["honesty"]["lens_is_truth_core"] is False
    assert view["honesty"]["retention_applied"] is False
    text = render_event_retention_text(view)
    assert "[UNKNOWN]" in text
    assert "[APPLIED]" not in text
    assert "[HEALTHY]" not in text


def test_empty_report_file_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "retention-report.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RetentionError, match="malformed event-retention report"):
        read_report(vault)
    with pytest.raises(WebEventRetentionError, match="event-retention-report-unreadable"):
        read_event_retention(vault)


def test_present_report_is_visible_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    written = _write_sample_report(vault, status="no-op")
    view = read_event_retention(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["report_present"] is True
    assert view["report_status"] == written["status"]
    assert view["report"] == written
    assert view["honesty"]["report_is_authority"] is False
    assert view["honesty"]["retention_report_is_apply"] is False
    assert view["honesty"]["applied_status_is_live_apply"] is False
    assert view["truth_boundary"] == TRUTH_BOUNDARY


def test_read_does_not_write_or_apply(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_unit(vault, "proj-a", "AE-001")
    _write_unit(vault, "proj-a", "AE-002")
    policy = default_policy(max_packages=1, max_bytes=10_000_000)
    policy_path = vault / ".atlas" / "retention-policy.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(
        json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    concept = vault / "projects" / "proj-a" / "concepts" / "note.md"
    concept.parent.mkdir(parents=True)
    concept.write_text("# keep me\n", encoding="utf-8")
    before = _snapshot(vault)
    view = read_event_retention(vault)
    assert view["reason_code"] == "REPORT_ABSENT"
    assert _snapshot(vault) == before
    assert not (vault / "generated" / "ops" / "retention-report.json").exists()
    assert (vault / "sources" / "agent-events" / "proj-a" / "AE-001").is_dir()
    assert (vault / "sources" / "agent-events" / "proj-a" / "AE-002").is_dir()
    assert concept.is_file()


def test_read_of_present_report_does_not_rewrite(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_sample_report(vault, status="applied", applied=True)
    before = _snapshot(vault)
    read_event_retention(vault)
    read_report(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_sample_report(vault)
    first = read_event_retention(vault)
    second = read_event_retention(vault)
    assert first == second


def test_symlink_report_is_path_escape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside-report.json"
    outside.write_text('{"hijack": true}\n', encoding="utf-8")
    target = vault / "generated" / "ops" / "retention-report.json"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(RetentionError, match="not a regular file"):
        read_report(vault)
    with pytest.raises(WebEventRetentionError, match="event-retention-report-unreadable"):
        read_event_retention(vault)


def test_vault_bind_does_not_import_sibling_report(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _write_sample_report(left)
    left_view = read_event_retention(left)
    right_view = read_event_retention(right)
    assert left_view["status"] == "PRESENT"
    assert right_view["status"] == "UNKNOWN"
    assert right_view["report"] is None
    assert right_view["available"] is False


def test_appservice_event_retention(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.event_retention()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_missing_report(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["retention", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    assert main(["retention", "show", "--vault", str(vault), "--json"]) == EXIT_OK


def test_cli_report_does_not_apply(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_unit(vault, "proj-a", "AE-001")
    _write_unit(vault, "proj-a", "AE-002")
    policy = default_policy(max_packages=1, max_bytes=10_000_000)
    policy_path = vault / ".atlas" / "retention-policy.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(
        json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    before = _snapshot(vault)
    assert main(["retention", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before
    assert (vault / "sources" / "agent-events" / "proj-a" / "AE-001").is_dir()
    assert (vault / "sources" / "agent-events" / "proj-a" / "AE-002").is_dir()


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["retention", "report", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_existing_retention_apply_cli_unchanged() -> None:
    from project_atlas.cli import build_parser

    parser = build_parser()
    help_text = parser.format_help()
    assert "retention" in help_text
    write_args = parser.parse_args(["retention", "apply", "--vault", "/tmp/vault"])
    assert write_args.retention_command == "apply"
    read_args = parser.parse_args(["retention", "report", "--vault", "/tmp/vault"])
    assert read_args.retention_command == "report"
    show_args = parser.parse_args(["retention", "show", "--vault", "/tmp/vault"])
    assert show_args.retention_command == "show"


def test_apply_still_writes_and_read_does_not_reapply(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_unit(vault, "proj-a", "AE-001")
    _write_unit(vault, "proj-a", "AE-002")
    written = apply_event_retention(vault, max_packages=1, max_bytes=10_000_000)
    assert written["applied"] is True
    before = _snapshot(vault)
    view = read_event_retention(vault)
    assert view["report_status"] == "applied"
    assert view["report_applied"] is True
    assert view["honesty"]["retention_applied"] is False
    assert view["honesty"]["applied_status_is_live_apply"] is False
    assert _snapshot(vault) == before


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.event.retention.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.event.retention.write" not in listing["tools"]
    assert "atlas.event.retention.apply" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.event.retention.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["retention_report_is_apply"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.event.retention.read", "args": {"apply": True}}
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.event.retention.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.event.retention.read", operator=bare)


def test_api_event_retention_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_sample_report(vault, status="dry-run", dry_run=True)
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(
            Request(f"http://{host}:{port}/v1/meta", headers=auth), timeout=2
        ) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["event_retention_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/event-retention", headers=auth),
            timeout=2,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "PRESENT"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
        assert body["honesty"]["retention_applied"] is False
    finally:
        server.shutdown()


def test_api_event_retention_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/event-retention",
            data=b"{}",
            headers={**auth, "Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 405
    finally:
        server.shutdown()


def test_d149_surfaces_untouched() -> None:
    root = Path(__file__).resolve().parents[2]
    authentic = (
        root / "src/project_atlas/orchestration/autonomy/authentic_estate.py"
    ).read_text(encoding="utf-8")
    reconciler = (
        root / "src/project_atlas/orchestration/sdk/mission_reconciler.py"
    ).read_text(encoding="utf-8")
    assert "AS-CODER-ALPHA-EVENT-RETENTION-READ-001" not in authentic
    assert "AS-CODER-ALPHA-EVENT-RETENTION-READ-001" not in reconciler
    assert "event_retention" not in reconciler
