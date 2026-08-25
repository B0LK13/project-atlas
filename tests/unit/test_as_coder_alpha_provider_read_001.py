"""AS-CODER-ALPHA-PROVIDER-READ-001 -- vault-scoped provider REPORT READ."""

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
from project_atlas.provider_adapters import (
    ProviderAdapter,
    build_adapter_registry,
    quarantine_provider_output,
)
from project_atlas.web_api.provider import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    TOOL_ID,
    TRUTH_BOUNDARY,
    WebProviderError,
    read_provider,
    render_provider_text,
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


def _valid_registry() -> dict[str, object]:
    return {
        "schema_version": 1,
        "package_id": "AS-2.0-PROV-001",
        "compat_snapshot_id": "atlas-1.0.0-compat",
        "adapters_enabled": False,
        "adapters": [
            {
                "adapter_id": "openai-assist",
                "provider": "openai",
                "enabled": False,
                "capabilities": ["classify-assist", "summarize"],
                "status": "registered",
            }
        ],
        "authority": {
            "level": "derived",
            "note": "Provider adapters optional; disabled leaves MVP functional",
        },
        "truth_boundary": "PROVIDER ADAPTER \u2260 AUTHORITY / \u2260 PROVENANCE BYPASS",
        "generated": {"by": "project-atlas"},
    }


def _valid_quarantine(*, envelope_id: str = "env-1") -> dict[str, object]:
    return {
        "schema_version": 1,
        "package_id": "AS-2.0-PROV-001",
        "compat_snapshot_id": "atlas-1.0.0-compat",
        "envelope_id": envelope_id,
        "adapter_id": "openai-assist",
        "status": "rejected-disabled",
        "secret_scan": {
            "findings_count": 0,
            "content_redacted": True,
            "finding_kinds": [],
        },
        "payload_kind": "text",
        "payload_sha256": "0" * 64,
        "authority": {
            "level": "derived",
            "note": "Quarantined provider output never writes Layer B",
        },
        "truth_boundary": "QUARANTINED PROVIDER OUTPUT \u2260 AUTHORITY",
        "generated": {"by": "project-atlas"},
    }


def _write_present_registry(vault: Path) -> None:
    _write(
        vault / "generated" / "ops" / "provider-adapter-registry.json",
        _valid_registry(),
    )


def _write_present_quarantine(vault: Path, *, envelope_id: str = "env-1") -> None:
    _write(
        vault / "generated" / "ops" / "provider-quarantine" / f"{envelope_id}.json",
        _valid_quarantine(envelope_id=envelope_id),
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebProviderError, match="provider-vault-missing"):
        read_provider(tmp_path / "absent")


def test_missing_artifacts_are_unknown_not_enabled(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_provider(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["reason_code"] == "ARTIFACTS_ABSENT"
    assert view["artifacts"]["registry"]["status"] == "MISSING"
    assert view["artifacts"]["registry"]["adapters_enabled"] is False
    assert view["artifacts"]["quarantine"]["status"] == "MISSING"
    assert view["honesty"]["missing_is_enabled"] is False
    assert view["honesty"]["missing_is_healthy"] is False
    assert view["honesty"]["provider_is_authority"] is False
    assert view["honesty"]["registry_is_live_sdk"] is False
    assert view["honesty"]["quarantine_is_approved"] is False
    assert view["honesty"]["live_sdk_enabled"] is False
    assert view["honesty"]["generate_dispatched"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["D149_TOUCHED"] == "NO"
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_provider_text(view)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "[ENABLED]" not in text
    assert "live_sdk:     false" in text
    assert all(ord(char) < 128 for char in text)


def test_empty_ops_dir_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "generated" / "ops").mkdir(parents=True)
    view = read_provider(vault)
    assert view["status"] == "EMPTY"
    assert view["reason_code"] == "ARTIFACTS_EMPTY"
    assert view["available"] is False
    assert view["honesty"]["empty_is_healthy"] is False
    assert view["artifacts"]["registry"]["status"] == "EMPTY"
    assert view["artifacts"]["registry"]["adapter_count"] == 0
    assert view["artifacts"]["quarantine"]["status"] == "MISSING"
    text = render_provider_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert "[ENABLED]" not in text


def test_empty_quarantine_dir_without_registry_is_empty(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "generated" / "ops" / "provider-quarantine").mkdir(parents=True)
    view = read_provider(vault)
    assert view["status"] == "EMPTY"
    assert view["available"] is False
    assert view["artifacts"]["quarantine"]["status"] == "EMPTY"
    assert view["honesty"]["empty_is_healthy"] is False


def test_malformed_registry_json_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "provider-adapter-registry.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(WebProviderError, match="provider-malformed-json"):
        read_provider(vault)


def test_empty_registry_object_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "provider-adapter-registry.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(WebProviderError, match="provider-malformed-record"):
        read_provider(vault)


def test_claimed_live_registry_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    payload = _valid_registry()
    payload["adapters_enabled"] = True
    _write(vault / "generated" / "ops" / "provider-adapter-registry.json", payload)
    with pytest.raises(WebProviderError, match="provider-malformed-record"):
        read_provider(vault)


def test_malformed_quarantine_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "provider-quarantine" / "env-bad.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(WebProviderError, match="provider-malformed-record"):
        read_provider(vault)


def test_present_registry_is_visible_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_registry(vault)
    view = read_provider(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["reason_code"] == "ARTIFACTS_PRESENT"
    registry = view["artifacts"]["registry"]
    assert registry["adapters_enabled"] is False
    assert registry["adapter_ids"] == ["openai-assist"]
    assert registry["records"][0]["enabled"] is False
    assert view["honesty"]["provider_is_authority"] is False
    assert view["honesty"]["registry_is_live_sdk"] is False
    assert view["honesty"]["live_sdk_enabled"] is False
    assert view["honesty"]["generate_dispatched"] is False
    assert view["truth_boundary"] == TRUTH_BOUNDARY
    text = render_provider_text(view)
    assert "[PRESENT]" in text
    assert "[ENABLED]" not in text
    assert "[HEALTHY]" not in text
    assert all(ord(char) < 128 for char in text)


def test_present_quarantine_is_visible_not_approved(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_quarantine(vault)
    view = read_provider(vault)
    assert view["status"] == "PRESENT"
    quarantine = view["artifacts"]["quarantine"]
    assert quarantine["envelope_ids"] == ["env-1"]
    assert quarantine["records"][0]["status"] == "rejected-disabled"
    assert quarantine["records"][0]["content_redacted"] is True
    assert "payload_text" not in json.dumps(view, sort_keys=True)
    assert view["honesty"]["quarantine_is_approved"] is False


def test_writer_persisted_artifacts_are_readable(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    build_adapter_registry(
        vault,
        adapters=[
            ProviderAdapter(
                adapter_id="openai-assist",
                provider="openai",
                capabilities=("classify-assist", "summarize"),
            )
        ],
    )
    quarantine_provider_output(
        vault,
        envelope_id="env-writer",
        adapter_id="openai-assist",
        payload_text="hello world",
        adapters_enabled=False,
    )
    view = read_provider(vault)
    assert view["status"] == "PRESENT"
    assert view["artifacts"]["registry"]["path"] == (
        "generated/ops/provider-adapter-registry.json"
    )
    assert view["artifacts"]["registry"]["adapters_enabled"] is False
    assert view["artifacts"]["quarantine"]["envelope_ids"] == ["env-writer"]
    assert view["honesty"]["registry_written"] is False
    assert view["honesty"]["quarantine_written"] is False


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    view = read_provider(vault)
    assert view["reason_code"] == "ARTIFACTS_ABSENT"
    assert _snapshot(vault) == before
    assert not (vault / "generated" / "ops" / "provider-adapter-registry.json").exists()
    assert not (vault / "generated" / "ops" / "provider-quarantine").exists()


def test_read_of_present_report_does_not_rewrite(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_registry(vault)
    _write_present_quarantine(vault)
    before = _snapshot(vault)
    read_provider(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_registry(vault)
    first = read_provider(vault)
    second = read_provider(vault)
    assert first == second
    encoded = json.dumps(first, indent=2, sort_keys=True)
    assert encoded == json.dumps(second, indent=2, sort_keys=True)


def test_symlink_registry_is_path_escape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside-registry.json"
    outside.write_text(json.dumps(_valid_registry()) + "\n", encoding="utf-8")
    target = vault / "generated" / "ops" / "provider-adapter-registry.json"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(WebProviderError, match="provider-not-regular-file"):
        read_provider(vault)


def test_symlink_quarantine_is_path_escape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside-envelope.json"
    outside.write_text(json.dumps(_valid_quarantine()) + "\n", encoding="utf-8")
    target = vault / "generated" / "ops" / "provider-quarantine" / "env-1.json"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(WebProviderError, match="provider-not-regular-file"):
        read_provider(vault)


def test_vault_bind_does_not_import_sibling_artifacts(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _write_present_registry(left)
    left_view = read_provider(left)
    right_view = read_provider(right)
    assert left_view["status"] == "PRESENT"
    assert right_view["status"] == "UNKNOWN"
    assert right_view["artifacts"]["registry"]["adapter_count"] == 0
    assert right_view["available"] is False


def test_reader_module_does_not_call_writers() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/provider.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "build_adapter_registry",
        "quarantine_provider_output",
        "run_local_model_adapter",
        "from project_atlas.provider_adapters",
        "from project_atlas.provider_live",
        "atlas.provider.generate",
        "openai",
        "anthropic",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_provider(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.provider()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_missing_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["provider", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "UNKNOWN"
    assert main(["provider", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["provider", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["provider", "report", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_existing_provider_writer_cli_unchanged() -> None:
    from project_atlas.cli import build_parser

    parser = build_parser()
    registry = parser.parse_args(
        [
            "provider",
            "registry",
            "--vault",
            "/tmp/vault",
            "--adapter",
            "openai-assist|openai|classify-assist",
        ]
    )
    assert registry.provider_command == "registry"
    assert Path(registry.vault) == Path("/tmp/vault")
    quarantine = parser.parse_args(
        [
            "provider",
            "quarantine",
            "--vault",
            "/tmp/vault",
            "--envelope-id",
            "env-1",
            "--adapter-id",
            "openai-assist",
            "--text",
            "hello",
        ]
    )
    assert quarantine.provider_command == "quarantine"
    assert quarantine.envelope_id == "env-1"
    read_args = parser.parse_args(["provider", "report", "--vault", "/tmp/vault"])
    assert read_args.command == "provider"
    assert read_args.provider_command == "report"
    show_args = parser.parse_args(["provider", "show", "--vault", "/tmp/vault"])
    assert show_args.provider_command == "show"


def test_cli_provider_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["provider", "--help"])
    assert exit_info.value.code == 0
    parent = capsys.readouterr().out
    assert all(ord(char) < 128 for char in parent)
    parent_flat = " ".join(parent.split())
    assert "persisted-report read" in parent_flat
    assert "never live SDK" in parent_flat
    with pytest.raises(SystemExit) as report_info:
        main(["provider", "report", "--help"])
    assert report_info.value.code == 0
    report = capsys.readouterr().out
    assert all(ord(char) < 128 for char in report)
    with pytest.raises(SystemExit) as show_info:
        main(["provider", "show", "--help"])
    assert show_info.value.code == 0
    show = capsys.readouterr().out
    assert all(ord(char) < 128 for char in show)
    with pytest.raises(SystemExit) as registry_info:
        main(["provider", "registry", "--help"])
    assert registry_info.value.code == 0
    registry = capsys.readouterr().out
    assert all(ord(char) < 128 for char in registry)
    registry_flat = " ".join(registry.split())
    assert "--adapter" in registry_flat
    assert "enabled forced false" in registry_flat
    with pytest.raises(SystemExit) as quarantine_info:
        main(["provider", "quarantine", "--help"])
    assert quarantine_info.value.code == 0
    quarantine = capsys.readouterr().out
    assert all(ord(char) < 128 for char in quarantine)
    quarantine_flat = " ".join(quarantine.split())
    assert "--envelope-id" in quarantine_flat
    assert "--adapter-id" in quarantine_flat


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert TOOL_ID == "atlas.provider.read"
    assert TOOL_ID in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.provider.generate" not in listing["tools"]
    assert "atlas.obs.read" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.provider.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["write_applied"] is False
    assert result["honesty"]["generate_dispatched"] is False


def test_mcp_generate_remains_denied(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(McpServerError, match="mcp-tool-denied"):
        invoke_mcp_tool(vault, "atlas.provider.generate")


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.provider.read", "args": {"generate": True}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.provider.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.provider.read", operator=bare)


def test_api_provider_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_present_registry(vault)
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
        assert meta["provider_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/provider", headers=auth),
            timeout=2,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "PRESENT"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
        assert body["honesty"]["WRITE_APPLIED"] is False
        assert body["honesty"]["registry_is_live_sdk"] is False
        assert body["honesty"]["live_sdk_enabled"] is False
    finally:
        server.shutdown()


def test_api_provider_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/provider",
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
    assert "AS-CODER-ALPHA-PROVIDER-READ-001" not in authentic
    assert "AS-CODER-ALPHA-PROVIDER-READ-001" not in reconciler
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-PROVIDER-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )


def test_does_not_implement_obs_or_sibling_wraps() -> None:
    root = Path(__file__).resolve().parents[2]
    registry = (root / "src/project_atlas/mcp_registry.py").read_text(encoding="utf-8")
    dispatch = (root / "src/project_atlas/mcp_server.py").read_text(encoding="utf-8")
    assert "atlas.obs.read" not in registry
    assert "atlas.obs.read" not in dispatch
    assert "atlas.kci.read" not in registry
    assert "atlas.lifecycle.read" not in registry
    assert "atlas.xproj.read" not in registry
    assert "atlas.schema.compat.read" not in registry
