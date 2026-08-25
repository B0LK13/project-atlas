"""AS-CODER-ALPHA-KF2-READ-001 -- vault-scoped Knowledge Fabric REPORT READ."""

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
from project_atlas.kf2_fabric import (
    register_entity,
    register_namespace,
    register_relationship,
)
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.kf2 import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    WebKf2Error,
    read_kf2,
    render_kf2_text,
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


def _namespace_payload(
    namespace_id: str = "portfolio",
    display_name: str = "Portfolio",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "package_id": "AS-KF2-NS-001",
        "namespace_id": namespace_id,
        "display_name": display_name,
        "compat_snapshot_id": "atlas-1.0.0-compat",
        "authority": {
            "level": "derived",
            "note": "KF2 namespace is fabric organization only",
        },
        "status": "active",
        "truth_boundary": "KF2 NAMESPACE \u2260 AUTHORITY",
    }


def _entity_payload(
    entity_id: str = "svc-api",
    namespace_id: str = "portfolio",
    display_name: str = "API Service",
    xproj_global_entity_id: str | None = "global-api-1",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "package_id": "AS-KF2-ENTITY-001",
        "entity_id": entity_id,
        "namespace_id": namespace_id,
        "display_name": display_name,
        "compat_snapshot_id": "atlas-1.0.0-compat",
        "authority": {
            "level": "derived",
            "note": "KF2 entity is derived fabric identity",
        },
        "status": "active",
        "truth_boundary": "KF2 ENTITY \u2260 AUTHORITY",
    }
    if xproj_global_entity_id:
        payload["xproj_global_entity_id"] = xproj_global_entity_id
    return payload


def _relationship_payload(
    relationship_id: str = "rel-web-depends-api",
    from_entity_id: str = "svc-web",
    to_entity_id: str = "svc-api",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "package_id": "AS-KF2-REL-001",
        "relationship_id": relationship_id,
        "from_entity_id": from_entity_id,
        "to_entity_id": to_entity_id,
        "relation_type": "depends-on",
        "compat_snapshot_id": "atlas-1.0.0-compat",
        "authority": {
            "level": "derived",
            "note": "KF2 relationship is derived; Graph!=authority",
        },
        "status": "active",
        "truth_boundary": "KF2 RELATIONSHIP \u2260 AUTHORITY",
    }


def _write_present_artifacts(vault: Path) -> None:
    _write(
        vault / "generated" / "kf2" / "namespaces" / "portfolio.json",
        _namespace_payload(),
    )
    _write(
        vault / "generated" / "kf2" / "entities" / "svc-api.json",
        _entity_payload(),
    )
    _write(
        vault / "generated" / "kf2" / "entities" / "svc-web.json",
        _entity_payload(
            entity_id="svc-web",
            display_name="Web Service",
            xproj_global_entity_id=None,
        ),
    )
    _write(
        vault / "generated" / "kf2" / "relationships" / "rel-web-depends-api.json",
        _relationship_payload(),
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebKf2Error, match="kf2-vault-missing"):
        read_kf2(tmp_path / "absent")


def test_missing_artifacts_are_unknown_not_registered(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_kf2(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["reason_code"] == "ARTIFACTS_ABSENT"
    assert view["artifacts"]["namespaces"]["status"] == "MISSING"
    assert view["artifacts"]["entities"]["status"] == "MISSING"
    assert view["artifacts"]["relationships"]["status"] == "MISSING"
    assert view["honesty"]["missing_is_registered"] is False
    assert view["honesty"]["missing_is_healthy"] is False
    assert view["honesty"]["kf2_is_authority"] is False
    assert view["honesty"]["name_is_identity"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["D149_TOUCHED"] == "NO"
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_kf2_text(view)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "[REGISTERED]" not in text
    assert all(ord(char) < 128 for char in text)


def test_empty_dirs_are_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "generated" / "kf2" / "namespaces").mkdir(parents=True)
    (vault / "generated" / "kf2" / "entities").mkdir(parents=True)
    (vault / "generated" / "kf2" / "relationships").mkdir(parents=True)
    view = read_kf2(vault)
    assert view["status"] == "EMPTY"
    assert view["reason_code"] == "ARTIFACTS_EMPTY"
    assert view["available"] is False
    assert view["honesty"]["empty_is_healthy"] is False
    assert view["artifacts"]["namespaces"]["status"] == "EMPTY"
    assert view["artifacts"]["namespaces"]["count"] == 0
    text = render_kf2_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert "[REGISTERED]" not in text


def test_malformed_json_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "kf2" / "namespaces" / "broken.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(WebKf2Error, match="kf2-malformed-json"):
        read_kf2(vault)


def test_empty_object_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "kf2" / "namespaces" / "empty.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(WebKf2Error, match="kf2-malformed-record"):
        read_kf2(vault)


def test_present_artifacts_are_visible_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_artifacts(vault)
    view = read_kf2(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["reason_code"] == "ARTIFACTS_PRESENT"
    assert view["artifacts"]["namespaces"]["namespace_ids"] == ["portfolio"]
    assert view["artifacts"]["entities"]["entity_ids"] == ["svc-api", "svc-web"]
    assert view["artifacts"]["relationships"]["relationship_ids"] == [
        "rel-web-depends-api"
    ]
    entity = view["artifacts"]["entities"]["records"][0]
    assert entity["entity_id"] == "svc-api"
    assert entity["display_name"] == "API Service"
    assert entity["entity_id"] != entity["display_name"]
    assert view["honesty"]["kf2_is_authority"] is False
    assert view["honesty"]["name_is_identity"] is False
    assert view["honesty"]["register_dispatched"] is False
    assert view["truth_boundary"] == TRUTH_BOUNDARY


def test_name_is_not_identity(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write(
        vault / "generated" / "kf2" / "namespaces" / "alpha.json",
        _namespace_payload(namespace_id="alpha", display_name="Shared Name"),
    )
    _write(
        vault / "generated" / "kf2" / "namespaces" / "beta.json",
        _namespace_payload(namespace_id="beta", display_name="Shared Name"),
    )
    view = read_kf2(vault)
    ids = view["artifacts"]["namespaces"]["namespace_ids"]
    assert ids == ["alpha", "beta"]
    names = [row["display_name"] for row in view["artifacts"]["namespaces"]["records"]]
    assert names == ["Shared Name", "Shared Name"]
    assert view["honesty"]["name_is_identity"] is False


def test_writer_persisted_artifacts_are_readable(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    register_namespace(vault, namespace_id="portfolio", display_name="Portfolio")
    register_entity(
        vault,
        entity_id="svc-api",
        namespace_id="portfolio",
        display_name="API Service",
        xproj_global_entity_id="global-api-1",
    )
    register_entity(
        vault,
        entity_id="svc-web",
        namespace_id="portfolio",
        display_name="Web Service",
    )
    register_relationship(
        vault,
        relationship_id="rel-web-depends-api",
        from_entity_id="svc-web",
        to_entity_id="svc-api",
        relation_type="depends-on",
    )
    view = read_kf2(vault)
    assert view["status"] == "PRESENT"
    assert view["artifacts"]["namespaces"]["namespace_ids"] == ["portfolio"]
    assert view["artifacts"]["entities"]["entity_ids"] == ["svc-api", "svc-web"]
    assert view["artifacts"]["relationships"]["relationship_ids"] == [
        "rel-web-depends-api"
    ]
    assert view["honesty"]["register_dispatched"] is False


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    view = read_kf2(vault)
    assert view["reason_code"] == "ARTIFACTS_ABSENT"
    assert _snapshot(vault) == before
    assert not (vault / "generated" / "kf2").exists()


def test_read_of_present_artifacts_does_not_rewrite(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_artifacts(vault)
    before = _snapshot(vault)
    read_kf2(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_artifacts(vault)
    first = read_kf2(vault)
    second = read_kf2(vault)
    assert first == second
    encoded = json.dumps(first, indent=2, sort_keys=True)
    assert encoded == json.dumps(second, indent=2, sort_keys=True)


def test_symlink_artifact_is_path_escape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside-namespace.json"
    outside.write_text(json.dumps(_namespace_payload()) + "\n", encoding="utf-8")
    target = vault / "generated" / "kf2" / "namespaces" / "hijack.json"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(WebKf2Error, match="kf2-not-regular-file"):
        read_kf2(vault)


def test_vault_bind_does_not_import_sibling_artifacts(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _write_present_artifacts(left)
    left_view = read_kf2(left)
    right_view = read_kf2(right)
    assert left_view["status"] == "PRESENT"
    assert right_view["status"] == "UNKNOWN"
    assert right_view["artifacts"]["namespaces"]["count"] == 0
    assert right_view["available"] is False


def test_reader_module_does_not_call_writers() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/kf2.py").read_text(encoding="utf-8")
    forbidden = (
        "register_namespace",
        "register_entity",
        "register_relationship",
        "build_kf2_fabric_inventory",
        "_atomic_write_json",
        "from project_atlas.kf2_fabric",
        "from project_atlas.kf2_inventory",
        "kf2_fabric",
        "kf2_inventory",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_kf2(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.kf2()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_missing_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["kf2", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "UNKNOWN"
    assert main(["kf2", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["kf2", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["kf2", "report", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_existing_kf2_write_cli_unchanged() -> None:
    from project_atlas.cli import build_parser

    parser = build_parser()
    write_ns = parser.parse_args(
        [
            "kf2",
            "namespace",
            "--vault",
            "/tmp/vault",
            "--id",
            "portfolio",
            "--name",
            "Portfolio",
        ]
    )
    assert write_ns.kf2_command == "namespace"
    write_entity = parser.parse_args(
        [
            "kf2",
            "entity",
            "--vault",
            "/tmp/vault",
            "--id",
            "svc-api",
            "--namespace",
            "portfolio",
            "--name",
            "API Service",
        ]
    )
    assert write_entity.kf2_command == "entity"
    write_rel = parser.parse_args(
        [
            "kf2",
            "rel",
            "--vault",
            "/tmp/vault",
            "--id",
            "rel-web-depends-api",
            "--from",
            "svc-web",
            "--to",
            "svc-api",
            "--type",
            "depends-on",
        ]
    )
    assert write_rel.kf2_command == "rel"
    read_args = parser.parse_args(["kf2", "report", "--vault", "/tmp/vault"])
    assert read_args.command == "kf2"
    assert read_args.kf2_command == "report"
    show_args = parser.parse_args(["kf2", "show", "--vault", "/tmp/vault"])
    assert show_args.kf2_command == "show"


def test_cli_kf2_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["kf2", "--help"])
    assert exit_info.value.code == 0
    parent = capsys.readouterr().out
    assert all(ord(char) < 128 for char in parent)
    with pytest.raises(SystemExit) as report_info:
        main(["kf2", "report", "--help"])
    assert report_info.value.code == 0
    report = capsys.readouterr().out
    assert all(ord(char) < 128 for char in report)
    with pytest.raises(SystemExit) as show_info:
        main(["kf2", "show", "--help"])
    assert show_info.value.code == 0
    show = capsys.readouterr().out
    assert all(ord(char) < 128 for char in show)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.kf2.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.kf2.write" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.kf2.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["write_applied"] is False
    assert result["honesty"]["missing_is_registered"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.kf2.read", "args": {"register": True}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.kf2.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.kf2.read", operator=bare)


def test_api_kf2_route(tmp_path: Path) -> None:
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
        assert meta["kf2_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/kf2", headers=auth),
            timeout=2,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "PRESENT"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
        assert body["honesty"]["WRITE_APPLIED"] is False
        assert body["honesty"]["name_is_identity"] is False
    finally:
        server.shutdown()


def test_api_kf2_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/kf2",
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
    assert "AS-CODER-ALPHA-KF2-READ-001" not in authentic
    assert "AS-CODER-ALPHA-KF2-READ-001" not in reconciler
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-KF2-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
