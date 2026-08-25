"""AS-CODER-ALPHA-INVENTORY-DRIFT-READ-001 — vault-scoped freshness lens."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.inventory_drift_read import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    InventoryDriftReadError,
    build_inventory_drift_read,
    render_inventory_drift_read_text,
)
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.source_identity import canonical_source_sha256


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _write_manifest(
    vault: Path,
    root: Path,
    sources: list[dict[str, object]],
) -> None:
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"source_root": str(root), "sources": sources},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _fresh_pair(
    tmp_path: Path, project_id: str = "harbor"
) -> tuple[Path, Path, Path]:
    root = tmp_path / "src"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("# Harbor\n\nstable\n", encoding="utf-8")
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "README.md",
                "sha256": canonical_source_sha256(readme),
                "likely_project": project_id,
            }
        ],
    )
    return vault, root, readme


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(
        InventoryDriftReadError, match="inventory-drift-vault-missing"
    ):
        build_inventory_drift_read(tmp_path / "absent")


def test_empty_vault_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = build_inventory_drift_read(vault)
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["reason_code"] == "NO_SCOPED_PROJECTS"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["honesty"]["stale_is_current"] is False
    assert report["honesty"]["owner_capability_granted"] is False
    assert report["honesty"]["authentic_pilot"] is False
    text = render_inventory_drift_read_text(report)
    assert "[UNKNOWN]" in text
    assert "[FRESH]" not in text
    assert "[HEALTHY]" not in text


def test_matching_sources_are_fresh(tmp_path: Path) -> None:
    vault, _root, _readme = _fresh_pair(tmp_path)
    report = build_inventory_drift_read(vault, "harbor")
    assert report["status"] == "FRESH"
    assert report["available"] is True
    assert report["project_id"] == "harbor"
    assert report["honesty"]["lens_is_authority"] is False
    assert report["honesty"]["owner_capability_granted"] is False


def test_changed_source_is_stale_not_current(tmp_path: Path) -> None:
    vault, _root, readme = _fresh_pair(tmp_path)
    readme.write_text("# Harbor\n\nchanged\n", encoding="utf-8")
    report = build_inventory_drift_read(vault, "harbor")
    assert report["status"] == "STALE"
    assert report["status"] != "FRESH"
    assert "README.md" in report["changed_paths"]
    assert report["honesty"]["stale_is_current"] is False


def test_missing_project_is_unknown(tmp_path: Path) -> None:
    vault, _root, _readme = _fresh_pair(tmp_path)
    report = build_inventory_drift_read(vault, "portal")
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["status"] != "FRESH"


def test_sentinel_project_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault, _root, _readme = _fresh_pair(tmp_path)
    report = build_inventory_drift_read(vault, "unknown-project")
    assert report["status"] == "UNKNOWN"
    assert report["reason_code"] == "SENTINEL_PROJECT"
    assert report["honesty"]["unknown_is_fresh"] is False


def test_sibling_project_not_leaked(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    harbor = root / "harbor.md"
    portal = root / "portal.md"
    harbor.write_text("harbor\n", encoding="utf-8")
    portal.write_text("portal-changed\n", encoding="utf-8")
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "harbor.md",
                "sha256": canonical_source_sha256(harbor),
                "likely_project": "harbor",
            },
            {
                "path": "portal.md",
                "sha256": "0" * 64,
                "likely_project": "portal",
            },
        ],
    )
    harbor_report = build_inventory_drift_read(vault, "harbor")
    portal_report = build_inventory_drift_read(vault, "portal")
    assert harbor_report["status"] == "FRESH"
    assert "portal.md" not in harbor_report["changed_paths"]
    assert portal_report["status"] == "STALE"
    assert "harbor.md" not in portal_report["changed_paths"]


def test_vault_scoped_stale_wins_over_fresh(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    harbor = root / "harbor.md"
    portal = root / "portal.md"
    harbor.write_text("harbor\n", encoding="utf-8")
    portal.write_text("portal\n", encoding="utf-8")
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "harbor.md",
                "sha256": canonical_source_sha256(harbor),
                "likely_project": "harbor",
            },
            {
                "path": "portal.md",
                "sha256": "0" * 64,
                "likely_project": "portal",
            },
        ],
    )
    report = build_inventory_drift_read(vault)
    assert report["status"] == "STALE"
    assert report["reason_code"] == "SOURCE_INVENTORY_STALE"
    assert report["project_count"] == 2


def test_vault_scoped_unknown_plus_fresh_is_not_fresh(tmp_path: Path) -> None:
    vault, _root, _readme = _fresh_pair(tmp_path)
    report = build_inventory_drift_read(
        vault, extra_project_ids=["missing-sibling"]
    )
    assert report["status"] == "UNKNOWN"
    assert report["status"] != "FRESH"
    assert report["reason_code"] == "MIXED_OR_UNKNOWN"


def test_malformed_manifest_is_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    report = build_inventory_drift_read(vault, "harbor")
    assert report["status"] == "UNKNOWN"
    assert report["reason_code"] == "MANIFEST_ABSENT"


def test_read_does_not_write(tmp_path: Path) -> None:
    vault, _root, readme = _fresh_pair(tmp_path)
    readme.write_text("# Harbor\n\nchanged\n", encoding="utf-8")
    before = _snapshot(vault)
    build_inventory_drift_read(vault, "harbor")
    build_inventory_drift_read(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault, _root, _readme = _fresh_pair(tmp_path)
    first = build_inventory_drift_read(vault, "harbor")
    second = build_inventory_drift_read(vault, "harbor")
    assert first == second


def test_cross_vault_inventory_is_not_imported(tmp_path: Path) -> None:
    left_root = tmp_path / "left"
    left_root.mkdir()
    left, _root, _readme = _fresh_pair(left_root)
    right = tmp_path / "right-vault"
    right.mkdir()
    report = build_inventory_drift_read(right, "harbor")
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    _ = left


def test_cli_json_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["inventory-drift", "--vault", str(vault), "--json"]) == EXIT_OK


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["inventory-drift", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_existing_connect_cli_unchanged() -> None:
    from project_atlas.cli import build_parser

    help_text = build_parser().format_help()
    assert "connect" in help_text
    assert "inventory-drift" in help_text


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.inventory.drift.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.inventory.drift.write" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.inventory.drift.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["unknown_is_fresh"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.inventory.drift.read", "args": {"fresh": True}}
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.inventory.drift.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.inventory.drift.read", operator=bare)


def test_api_inventory_drift_route(tmp_path: Path) -> None:
    vault, _root, _readme = _fresh_pair(tmp_path)
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
        assert meta["inventory_drift_live"] is True
        with urlopen(
            Request(
                f"http://{host}:{port}/v1/inventory-drift?project=harbor",
                headers=auth,
            ),
            timeout=2,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "FRESH"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
    finally:
        server.shutdown()


def test_api_inventory_drift_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/inventory-drift",
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
    """This package must not rewrite authentic-estate / owner-gate modules."""
    root = Path(__file__).resolve().parents[2]
    authentic = (
        root / "src/project_atlas/orchestration/autonomy/authentic_estate.py"
    ).read_text(encoding="utf-8")
    reconciler = (
        root / "src/project_atlas/orchestration/sdk/mission_reconciler.py"
    ).read_text(encoding="utf-8")
    assert "AS-CODER-ALPHA-INVENTORY-DRIFT-READ-001" not in authentic
    assert "AS-CODER-ALPHA-INVENTORY-DRIFT-READ-001" not in reconciler
    assert "inventory_drift_read" not in reconciler


def test_web_demo_stub_does_not_fabricate_fresh() -> None:
    """Demo hook must stay UNKNOWN — no invented FRESH or HEALTHY rows."""
    hook = (
        Path(__file__).resolve().parents[2]
        / "apps/web/src/hooks/useInventoryDrift.ts"
    ).read_text(encoding="utf-8")
    assert 'status: "UNKNOWN"' in hook
    assert 'reason_code: "DEMO_STUB_UNKNOWN"' in hook
    assert "available: false" in hook
    assert "demo_isolated: true" in hook
    assert 'status: "FRESH"' not in hook
    assert 'status: "HEALTHY"' not in hook
    assert "OWNER_CAPABILITY_GRANTED" not in hook
