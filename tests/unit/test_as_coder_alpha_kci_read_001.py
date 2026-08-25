"""AS-CODER-ALPHA-KCI-READ-001 -- vault-scoped Knowledge CI REPORT READ."""

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
from project_atlas.kci import build_compile_request, issue_compile_receipt
from project_atlas.knowledge_ci_harness import build_knowledge_ci_harness
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.kci import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    WebKciError,
    read_kci,
    render_kci_text,
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


def _request_payload(request_id: str = "compile-alpha") -> dict[str, object]:
    return {
        "schema_version": 1,
        "package_id": "AS-2.0-KCI-001",
        "compat_snapshot_id": "atlas-1.0.0-compat",
        "request_id": request_id,
        "operation": "compile",
        "fixture_mode": True,
        "source_refs": ["sources/fixture-a.md"],
        "authority": {
            "level": "derived",
            "note": "KCI compile request is consume-only; not Layer B authority",
        },
        "truth_boundary": "KCI COMPILE \u2260 AUTHORITY / \u2260 SILENT WINNER",
        "generated": {"by": "project-atlas"},
    }


def _receipt_payload(
    receipt_id: str = "receipt-alpha",
    request_id: str = "compile-alpha",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "package_id": "AS-2.0-KCI-001",
        "compat_snapshot_id": "atlas-1.0.0-compat",
        "receipt_id": receipt_id,
        "request_id": request_id,
        "status": "accepted",
        "consume_only": True,
        "authority_promoted": False,
        "authority": {
            "level": "derived",
            "note": "KCI receipt never promotes Layer B authority",
        },
        "truth_boundary": "KCI RECEIPT \u2260 LAYER B AUTHORITY",
        "generated": {"by": "project-atlas"},
    }


def _harness_payload(harness_id: str = "harness-alpha") -> dict[str, object]:
    return {
        "schema_version": 1,
        "package_id": "AS-2.0-KCI-HARNESS-001",
        "compat_snapshot_id": "atlas-1.0.0-compat",
        "harness_id": harness_id,
        "authority_promoted": False,
        "gates": [{"gate_id": "schema", "kind": "schema", "required": True}],
        "authority": {
            "level": "derived",
            "note": "Knowledge CI harness catalogs gates; never promotes authority",
        },
        "truth_boundary": "KNOWLEDGE CI HARNESS \u2260 AUTHORITY PROMOTE",
        "generated": {"by": "project-atlas"},
    }


def _write_present_artifacts(vault: Path) -> None:
    _write(
        vault / "generated" / "kci" / "compile-alpha-compile-request.json",
        _request_payload(),
    )
    _write(
        vault / "generated" / "kci" / "receipt-alpha-compile-receipt.json",
        _receipt_payload(),
    )
    _write(vault / "generated" / "ops" / "kci" / "harness-alpha.json", _harness_payload())


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebKciError, match="kci-vault-missing"):
        read_kci(tmp_path / "absent")


def test_missing_artifacts_are_unknown_not_pass(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_kci(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["reason_code"] == "ARTIFACTS_ABSENT"
    assert view["artifacts"]["compile_requests"]["status"] == "MISSING"
    assert view["artifacts"]["compile_receipts"]["status"] == "MISSING"
    assert view["artifacts"]["harness_records"]["status"] == "MISSING"
    assert view["honesty"]["missing_is_pass"] is False
    assert view["honesty"]["missing_is_healthy"] is False
    assert view["honesty"]["kci_is_authority"] is False
    assert view["honesty"]["receipt_is_certification"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["D149_TOUCHED"] == "NO"
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_kci_text(view)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "[PASS]" not in text
    assert all(ord(char) < 128 for char in text)


def test_empty_dirs_are_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "generated" / "kci").mkdir(parents=True)
    (vault / "generated" / "ops" / "kci").mkdir(parents=True)
    view = read_kci(vault)
    assert view["status"] == "EMPTY"
    assert view["reason_code"] == "ARTIFACTS_EMPTY"
    assert view["available"] is False
    assert view["honesty"]["empty_is_healthy"] is False
    assert view["artifacts"]["compile_receipts"]["status"] == "EMPTY"
    assert view["artifacts"]["compile_receipts"]["count"] == 0
    text = render_kci_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert "[PASS]" not in text


def test_malformed_json_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "kci" / "broken-compile-receipt.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(WebKciError, match="kci-malformed-json"):
        read_kci(vault)


def test_empty_object_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "kci" / "empty-compile-receipt.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(WebKciError, match="kci-malformed-record"):
        read_kci(vault)


def test_present_artifacts_are_visible_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_artifacts(vault)
    view = read_kci(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["reason_code"] == "ARTIFACTS_PRESENT"
    assert view["artifacts"]["compile_requests"]["request_ids"] == ["compile-alpha"]
    assert view["artifacts"]["compile_receipts"]["receipt_ids"] == ["receipt-alpha"]
    assert view["artifacts"]["harness_records"]["harness_ids"] == ["harness-alpha"]
    receipt = view["artifacts"]["compile_receipts"]["records"][0]
    assert receipt["authority_promoted"] is False
    assert receipt["status"] == "accepted"
    assert view["honesty"]["kci_is_authority"] is False
    assert view["honesty"]["receipt_is_certification"] is False
    assert view["honesty"]["harness_executed"] is False
    assert view["honesty"]["request_issued"] is False
    assert view["truth_boundary"] == TRUTH_BOUNDARY


def test_writer_persisted_artifacts_are_readable(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    build_compile_request(
        request_id="compile-live",
        source_refs=["sources/live.md"],
        output_vault=vault,
    )
    issue_compile_receipt(
        receipt_id="receipt-live",
        request_id="compile-live",
        output_vault=vault,
    )
    build_knowledge_ci_harness(vault, record_id="harness-live")
    view = read_kci(vault)
    assert view["status"] == "PRESENT"
    assert view["artifacts"]["compile_requests"]["request_ids"] == ["compile-live"]
    assert view["artifacts"]["compile_receipts"]["receipt_ids"] == ["receipt-live"]
    assert view["artifacts"]["harness_records"]["harness_ids"] == ["harness-live"]


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    view = read_kci(vault)
    assert view["reason_code"] == "ARTIFACTS_ABSENT"
    assert _snapshot(vault) == before
    assert not (vault / "generated" / "kci").exists()
    assert not (vault / "generated" / "ops" / "kci").exists()


def test_read_of_present_artifacts_does_not_rewrite(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_artifacts(vault)
    before = _snapshot(vault)
    read_kci(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_artifacts(vault)
    first = read_kci(vault)
    second = read_kci(vault)
    assert first == second
    encoded = json.dumps(first, indent=2, sort_keys=True)
    assert encoded == json.dumps(second, indent=2, sort_keys=True)


def test_symlink_artifact_is_path_escape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside-receipt.json"
    outside.write_text(json.dumps(_receipt_payload()) + "\n", encoding="utf-8")
    target = vault / "generated" / "kci" / "hijack-compile-receipt.json"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(WebKciError, match="kci-not-regular-file"):
        read_kci(vault)


def test_vault_bind_does_not_import_sibling_artifacts(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _write_present_artifacts(left)
    left_view = read_kci(left)
    right_view = read_kci(right)
    assert left_view["status"] == "PRESENT"
    assert right_view["status"] == "UNKNOWN"
    assert right_view["artifacts"]["compile_receipts"]["count"] == 0
    assert right_view["available"] is False


def test_reader_module_does_not_call_writers() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/kci.py").read_text(encoding="utf-8")
    forbidden = (
        "build_compile_request",
        "issue_compile_receipt",
        "build_knowledge_ci_harness",
        "_atomic_write_json",
        "knowledge_ci_harness",
        "from project_atlas.kci",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_kci(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.kci()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_missing_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["kci", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "UNKNOWN"
    assert main(["kci", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["kci", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["kci", "report", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_existing_kci_write_cli_unchanged() -> None:
    from project_atlas.cli import build_parser

    parser = build_parser()
    write_req = parser.parse_args(
        [
            "kci",
            "request",
            "--request-id",
            "compile-alpha",
            "--source-ref",
            "sources/a.md",
            "--vault",
            "/tmp/vault",
        ]
    )
    assert write_req.kci_command == "request"
    write_receipt = parser.parse_args(
        [
            "kci",
            "receipt",
            "--receipt-id",
            "receipt-alpha",
            "--request-id",
            "compile-alpha",
            "--vault",
            "/tmp/vault",
        ]
    )
    assert write_receipt.kci_command == "receipt"
    read_args = parser.parse_args(["kci", "report", "--vault", "/tmp/vault"])
    assert read_args.command == "kci"
    assert read_args.kci_command == "report"
    show_args = parser.parse_args(["kci", "show", "--vault", "/tmp/vault"])
    assert show_args.kci_command == "show"


def test_cli_kci_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["kci", "--help"])
    assert exit_info.value.code == 0
    parent = capsys.readouterr().out
    assert all(ord(char) < 128 for char in parent)
    with pytest.raises(SystemExit) as report_info:
        main(["kci", "report", "--help"])
    assert report_info.value.code == 0
    report = capsys.readouterr().out
    assert all(ord(char) < 128 for char in report)
    with pytest.raises(SystemExit) as show_info:
        main(["kci", "show", "--help"])
    assert show_info.value.code == 0
    show = capsys.readouterr().out
    assert all(ord(char) < 128 for char in show)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.kci.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.kci.write" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.kci.read")
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
            json.dumps({"tool": "atlas.kci.read", "args": {"request": True}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.kci.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.kci.read", operator=bare)


def test_api_kci_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_artifacts(vault)
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
        assert meta["kci_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/kci", headers=auth),
            timeout=2,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "PRESENT"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
        assert body["honesty"]["WRITE_APPLIED"] is False
    finally:
        server.shutdown()


def test_api_kci_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/kci",
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
    assert "AS-CODER-ALPHA-KCI-READ-001" not in authentic
    assert "AS-CODER-ALPHA-KCI-READ-001" not in reconciler
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-KCI-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
