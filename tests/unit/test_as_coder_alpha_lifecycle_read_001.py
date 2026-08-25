"""AS-CODER-ALPHA-LIFECYCLE-READ-001 -- vault-scoped lifecycle REPORT READ."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.lifecycle_cert import write_report
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.lifecycle import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    WebLifecycleError,
    read_lifecycle,
    render_lifecycle_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _valid_report(*, status: str = "partial") -> dict[str, object]:
    cases = [
        {
            "case_id": "corrupt",
            "result": "pass",
            "expected": "fail-closed",
            "observed": "raised",
        },
        {
            "case_id": "new",
            "result": "pass",
            "expected": "new",
            "observed": "new",
        },
    ]
    return {
        "schema_version": 1,
        "schema": "atlas.lifecycle_cert.report.v1",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": "FIXTURE LIFECYCLE CERT \u2260 ESTATE PILOT PASS",
        "package": "AS-CORE2-010",
        "status": status,
        "estate_pilot_passed": False,
        "cases": cases,
        "counts": {"total": 2, "passed": 2, "failed": 0},
        "generated": {"by": "atlas-core2-010"},
    }


def _write_present_report(vault: Path, *, status: str = "partial") -> None:
    _write(
        vault / "generated" / "ops" / "lifecycle-cert-report.json",
        _valid_report(status=status),
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebLifecycleError, match="lifecycle-vault-missing"):
        read_lifecycle(tmp_path / "absent")


def test_missing_artifacts_are_unknown_not_certified(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_lifecycle(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["reason_code"] == "ARTIFACTS_ABSENT"
    assert view["artifacts"]["certify_report"]["status"] == "MISSING"
    assert view["artifacts"]["certify_report"]["estate_pilot_passed"] is False
    assert view["honesty"]["missing_is_certified"] is False
    assert view["honesty"]["missing_is_healthy"] is False
    assert view["honesty"]["lifecycle_is_authority"] is False
    assert view["honesty"]["certify_report_is_pilot_pass"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["D149_TOUCHED"] == "NO"
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_lifecycle_text(view)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "[CERTIFIED]" not in text
    assert "estate_pilot_passed: false" in text
    assert all(ord(char) < 128 for char in text)


def test_empty_ops_dir_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "generated" / "ops").mkdir(parents=True)
    view = read_lifecycle(vault)
    assert view["status"] == "EMPTY"
    assert view["reason_code"] == "ARTIFACTS_EMPTY"
    assert view["available"] is False
    assert view["honesty"]["empty_is_healthy"] is False
    assert view["artifacts"]["certify_report"]["status"] == "EMPTY"
    assert view["artifacts"]["certify_report"]["case_count"] == 0
    text = render_lifecycle_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert "[CERTIFIED]" not in text


def test_malformed_json_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "lifecycle-cert-report.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(WebLifecycleError, match="lifecycle-malformed-json"):
        read_lifecycle(vault)


def test_empty_object_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "lifecycle-cert-report.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(WebLifecycleError, match="lifecycle-malformed-record"):
        read_lifecycle(vault)


def test_claimed_pilot_pass_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    payload = _valid_report()
    payload["estate_pilot_passed"] = True
    _write(vault / "generated" / "ops" / "lifecycle-cert-report.json", payload)
    with pytest.raises(WebLifecycleError, match="lifecycle-malformed-record"):
        read_lifecycle(vault)


def test_present_report_is_visible_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_report(vault, status="certified")
    view = read_lifecycle(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["reason_code"] == "ARTIFACTS_PRESENT"
    report = view["artifacts"]["certify_report"]
    assert report["report_status"] == "certified"
    assert report["estate_pilot_passed"] is False
    assert report["case_ids"] == ["corrupt", "new"]
    assert report["package"] == "AS-CORE2-010"
    assert view["honesty"]["lifecycle_is_authority"] is False
    assert view["honesty"]["certify_report_is_pilot_pass"] is False
    assert view["honesty"]["certify_executed"] is False
    assert view["honesty"]["estate_pilot_passed"] is False
    assert view["truth_boundary"] == TRUTH_BOUNDARY
    text = render_lifecycle_text(view)
    assert "[PRESENT]" in text
    assert "[CERTIFIED]" not in text
    assert "[HEALTHY]" not in text
    assert all(ord(char) < 128 for char in text)


def test_writer_persisted_report_is_readable(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    write_report(vault, _valid_report())
    view = read_lifecycle(vault)
    assert view["status"] == "PRESENT"
    assert view["artifacts"]["certify_report"]["path"] == (
        "generated/ops/lifecycle-cert-report.json"
    )
    assert view["artifacts"]["certify_report"]["estate_pilot_passed"] is False
    assert view["honesty"]["report_written"] is False


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    view = read_lifecycle(vault)
    assert view["reason_code"] == "ARTIFACTS_ABSENT"
    assert _snapshot(vault) == before
    assert not (vault / "generated" / "ops" / "lifecycle-cert-report.json").exists()


def test_read_of_present_report_does_not_rewrite(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_report(vault)
    before = _snapshot(vault)
    read_lifecycle(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_report(vault)
    first = read_lifecycle(vault)
    second = read_lifecycle(vault)
    assert first == second
    encoded = json.dumps(first, indent=2, sort_keys=True)
    assert encoded == json.dumps(second, indent=2, sort_keys=True)


def test_symlink_artifact_is_path_escape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside-report.json"
    outside.write_text(json.dumps(_valid_report()) + "\n", encoding="utf-8")
    target = vault / "generated" / "ops" / "lifecycle-cert-report.json"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(WebLifecycleError, match="lifecycle-not-regular-file"):
        read_lifecycle(vault)


def test_vault_bind_does_not_import_sibling_artifacts(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _write_present_report(left)
    left_view = read_lifecycle(left)
    right_view = read_lifecycle(right)
    assert left_view["status"] == "PRESENT"
    assert right_view["status"] == "UNKNOWN"
    assert right_view["artifacts"]["certify_report"]["case_count"] == 0
    assert right_view["available"] is False


def test_reader_module_does_not_call_writers() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/lifecycle.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "run_fixture_lifecycle_certification",
        "write_report",
        "build_report",
        "_write_atomic",
        "from project_atlas.lifecycle_cert",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_lifecycle(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.lifecycle()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_missing_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["lifecycle", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "UNKNOWN"
    assert main(["lifecycle", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["lifecycle", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["lifecycle", "report", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_existing_lifecycle_certify_cli_unchanged() -> None:
    from project_atlas.cli import build_parser

    parser = build_parser()
    certify = parser.parse_args(
        [
            "lifecycle",
            "certify",
            "--work-root",
            "/tmp/work",
            "--report-vault",
            "/tmp/vault",
        ]
    )
    assert certify.lifecycle_command == "certify"
    assert Path(certify.work_root) == Path("/tmp/work")
    assert Path(certify.report_vault) == Path("/tmp/vault")
    read_args = parser.parse_args(["lifecycle", "report", "--vault", "/tmp/vault"])
    assert read_args.command == "lifecycle"
    assert read_args.lifecycle_command == "report"
    show_args = parser.parse_args(["lifecycle", "show", "--vault", "/tmp/vault"])
    assert show_args.lifecycle_command == "show"


def test_cli_lifecycle_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["lifecycle", "--help"])
    assert exit_info.value.code == 0
    parent = capsys.readouterr().out
    assert all(ord(char) < 128 for char in parent)
    with pytest.raises(SystemExit) as report_info:
        main(["lifecycle", "report", "--help"])
    assert report_info.value.code == 0
    report = capsys.readouterr().out
    assert all(ord(char) < 128 for char in report)
    with pytest.raises(SystemExit) as show_info:
        main(["lifecycle", "show", "--help"])
    assert show_info.value.code == 0
    show = capsys.readouterr().out
    assert all(ord(char) < 128 for char in show)
    with pytest.raises(SystemExit) as certify_info:
        main(["lifecycle", "certify", "--help"])
    assert certify_info.value.code == 0
    certify = capsys.readouterr().out
    assert all(ord(char) < 128 for char in certify)
    assert "fixture lifecycle matrix" in certify
    assert "write an ops report" in certify


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.lifecycle.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.lifecycle.write" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.lifecycle.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["write_applied"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.lifecycle.read", "args": {"certify": True}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.lifecycle.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.lifecycle.read", operator=bare)


def test_api_lifecycle_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_report(vault)
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
        assert meta["lifecycle_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/lifecycle", headers=auth),
            timeout=2,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "PRESENT"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
        assert body["honesty"]["WRITE_APPLIED"] is False
        assert body["honesty"]["certify_report_is_pilot_pass"] is False
    finally:
        server.shutdown()


def test_api_lifecycle_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/lifecycle",
            data=b"{}",
            headers={**auth, "Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 405
    finally:
        server.shutdown()


def test_d149_and_atlas3_untouched() -> None:
    root = Path(__file__).resolve().parents[2]
    authentic = (
        root / "src/project_atlas/orchestration/autonomy/authentic_estate.py"
    ).read_text(encoding="utf-8")
    reconciler = (
        root / "src/project_atlas/orchestration/sdk/mission_reconciler.py"
    ).read_text(encoding="utf-8")
    assert "AS-CODER-ALPHA-LIFECYCLE-READ-001" not in authentic
    assert "AS-CODER-ALPHA-LIFECYCLE-READ-001" not in reconciler
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-LIFECYCLE-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
