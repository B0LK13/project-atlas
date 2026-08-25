"""AS-CODER-ALPHA-XPROJ-READ-001 — vault-scoped REPORT READ lens."""

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
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.xproj import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    WebXprojError,
    read_xproj,
    render_xproj_text,
)
from project_atlas.xproj_duplicates import DuplicateCandidate
from project_atlas.xproj_edges import GlobalEdgeRecord
from project_atlas.xproj_registry import EvidenceRef, GlobalEntityRecord, JoinKeyRecord


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _write_present_projections(vault: Path) -> None:
    entity = GlobalEntityRecord(
        global_entity_id="postgres-global",
        entity_class="technology",
        display_name="PostgreSQL",
    )
    join = JoinKeyRecord(
        project_id="harbor-api",
        project_local_entity_id="pg-local",
        global_entity_id="postgres-global",
        evidence_refs=(
            EvidenceRef(relative_path="sources/harbor/adr.md", sha256=_digest("join")),
        ),
    )
    edge = GlobalEdgeRecord(
        edge_id="harbor-depends-on-postgres",
        relationship_type="depends-on",
        source_global_entity_id="harbor-api-svc",
        target_global_entity_id="postgres-global",
        evidence_refs=(
            EvidenceRef(relative_path="sources/harbor/adr.md", sha256=_digest("edge")),
        ),
        edge_fingerprint=_digest("edge-fp"),
        source_project_ids=("harbor-api",),
        target_project_ids=("shared-data",),
    )
    duplicate = DuplicateCandidate(
        candidate_id="dup-harbor-clone",
        category="canonical-remote-url-collision",
        reason="same canonical remote URL observed on two project ids",
        project_ids=("harbor-api", "harbor-api-clone"),
        signal="canonical-remote-url",
        inputs_considered={"canonical_remote_url": "https://example.invalid/harbor.git"},
    )
    entity_path = vault / "state" / "global-entities" / "postgres-global.json"
    join_path = vault / "state" / "global-entities" / "joins" / "harbor-join.json"
    edge_path = vault / "state" / "global-entities" / "edges" / "harbor-edge.json"
    dup_path = (
        vault / "generated" / "xproj" / "duplicate-candidates" / "dup-harbor-clone.json"
    )
    entity_path.parent.mkdir(parents=True, exist_ok=True)
    join_path.parent.mkdir(parents=True, exist_ok=True)
    edge_path.parent.mkdir(parents=True, exist_ok=True)
    dup_path.parent.mkdir(parents=True, exist_ok=True)
    entity_path.write_text(entity.to_json(), encoding="utf-8")
    join_path.write_text(join.to_json(), encoding="utf-8")
    edge_path.write_text(edge.to_json(), encoding="utf-8")
    dup_path.write_text(duplicate.to_json(), encoding="utf-8")


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebXprojError, match="xproj-vault-missing"):
        read_xproj(tmp_path / "absent")


def test_missing_projections_are_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_xproj(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["reason_code"] == "PROJECTIONS_ABSENT"
    assert view["projections"]["registry"]["status"] == "MISSING"
    assert view["projections"]["edges"]["status"] == "MISSING"
    assert view["projections"]["duplicates"]["status"] == "MISSING"
    assert view["honesty"]["missing_is_no_edges"] is False
    assert view["honesty"]["missing_is_healthy"] is False
    assert view["honesty"]["xproj_is_authority"] is False
    assert view["honesty"]["graph_is_authority"] is False
    assert view["honesty"]["lens_is_truth_core"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["D149_TOUCHED"] == "NO"
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_xproj_text(view)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "NO_EDGES" not in text


def test_empty_projection_dirs_are_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "state" / "global-entities" / "edges").mkdir(parents=True)
    (vault / "generated" / "xproj" / "duplicate-candidates").mkdir(parents=True)
    view = read_xproj(vault)
    assert view["status"] == "EMPTY"
    assert view["reason_code"] == "PROJECTIONS_EMPTY"
    assert view["available"] is False
    assert view["honesty"]["empty_is_healthy"] is False
    assert view["projections"]["edges"]["status"] == "EMPTY"
    assert view["projections"]["edges"]["edge_count"] == 0
    text = render_xproj_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert "[NO_EDGES]" not in text


def test_malformed_json_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "state" / "global-entities" / "broken.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(WebXprojError, match="xproj-malformed-json"):
        read_xproj(vault)


def test_empty_object_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "state" / "global-entities" / "empty.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(WebXprojError, match="xproj-malformed-record"):
        read_xproj(vault)


def test_present_projections_are_visible_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_projections(vault)
    view = read_xproj(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["reason_code"] == "PROJECTIONS_PRESENT"
    assert view["projections"]["registry"]["entity_ids"] == ["postgres-global"]
    assert view["projections"]["registry"]["join_count"] == 1
    assert view["projections"]["edges"]["edge_ids"] == ["harbor-depends-on-postgres"]
    assert view["projections"]["duplicates"]["candidate_ids"] == ["dup-harbor-clone"]
    assert view["honesty"]["xproj_is_authority"] is False
    assert view["honesty"]["identities_merged"] is False
    assert view["honesty"]["edges_written"] is False
    assert view["truth_boundary"] == TRUTH_BOUNDARY


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    view = read_xproj(vault)
    assert view["reason_code"] == "PROJECTIONS_ABSENT"
    assert _snapshot(vault) == before
    assert not (vault / "state" / "global-entities").exists()
    assert not (vault / "generated" / "xproj").exists()


def test_read_of_present_projections_does_not_rewrite(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_projections(vault)
    before = _snapshot(vault)
    read_xproj(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_projections(vault)
    first = read_xproj(vault)
    second = read_xproj(vault)
    assert first == second
    encoded = json.dumps(first, indent=2, sort_keys=True)
    assert encoded == json.dumps(second, indent=2, sort_keys=True)


def test_symlink_projection_is_path_escape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside-entity.json"
    outside.write_text('{"hijack": true}\n', encoding="utf-8")
    target = vault / "state" / "global-entities" / "hijack.json"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(WebXprojError, match="xproj-not-regular-file"):
        read_xproj(vault)


def test_vault_bind_does_not_import_sibling_projections(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _write_present_projections(left)
    left_view = read_xproj(left)
    right_view = read_xproj(right)
    assert left_view["status"] == "PRESENT"
    assert right_view["status"] == "UNKNOWN"
    assert right_view["projections"]["edges"]["edge_count"] == 0
    assert right_view["available"] is False


def test_reader_module_does_not_call_writers() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/xproj.py").read_text(encoding="utf-8")
    forbidden = (
        "write_registry_outputs",
        "write_edge_outputs",
        "write_duplicate_outputs",
        "apply_registrations",
        "apply_edge_registrations",
        "register_global_entity",
        "register_join",
        "register_global_edge",
        "detect_project_duplicates",
        "write_xproj_index_outputs",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_xproj(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.xproj()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_missing_projections(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["xproj", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "UNKNOWN"
    assert main(["xproj", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["xproj", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["xproj", "report", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_existing_xproj_write_cli_unchanged() -> None:
    from project_atlas.cli import build_parser

    parser = build_parser()
    help_text = parser.format_help()
    assert "xproj" in help_text
    write_args = parser.parse_args(
        ["register-global-entity", "--registrations", "/tmp/regs.json"]
    )
    assert write_args.command == "register-global-entity"
    read_args = parser.parse_args(["xproj", "report", "--vault", "/tmp/vault"])
    assert read_args.command == "xproj"
    assert read_args.xproj_command == "report"
    show_args = parser.parse_args(["xproj", "show", "--vault", "/tmp/vault"])
    assert show_args.xproj_command == "show"


def test_cli_xproj_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["xproj", "--help"])
    assert exit_info.value.code == 0
    parent = capsys.readouterr().out
    assert all(ord(char) < 128 for char in parent)
    with pytest.raises(SystemExit) as report_info:
        main(["xproj", "report", "--help"])
    assert report_info.value.code == 0
    report = capsys.readouterr().out
    assert all(ord(char) < 128 for char in report)
    with pytest.raises(SystemExit) as show_info:
        main(["xproj", "show", "--help"])
    assert show_info.value.code == 0
    show = capsys.readouterr().out
    assert all(ord(char) < 128 for char in show)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.xproj.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.xproj.write" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.xproj.read")
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
            json.dumps({"tool": "atlas.xproj.read", "args": {"join": True}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.xproj.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.xproj.read", operator=bare)


def test_api_xproj_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_projections(vault)
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
        assert meta["xproj_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/xproj", headers=auth),
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


def test_api_xproj_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/xproj",
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
    assert "AS-CODER-ALPHA-XPROJ-READ-001" not in authentic
    assert "AS-CODER-ALPHA-XPROJ-READ-001" not in reconciler
    assert "xproj" not in reconciler
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-XPROJ-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
