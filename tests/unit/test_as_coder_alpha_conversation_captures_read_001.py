"""AS-CODER-ALPHA-CONVERSATION-CAPTURES-READ-001 — vault-scoped capture lens."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.conversation_capture import (
    capture_conversation,
    set_conversation_review_state,
)
from project_atlas.conversation_captures_read import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    ConversationCapturesReadError,
    build_conversation_captures_read,
    render_conversation_captures_read_text,
)
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.session_capture import capture_session


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _vault_with_projects(root: Path, *project_ids: str) -> Path:
    vault = root / "vault"
    for project_id in project_ids:
        (vault / "projects" / project_id).mkdir(parents=True)
    return vault


def _envelope(
    *,
    project_id: str = "harbor-api",
    provider: str = "cursor",
    summary: str = "Standup notes for Harbor API",
) -> dict[str, Any]:
    return {
        "schema": "atlas.conversation-capture.v1",
        "schema_version": 1,
        "project_id": project_id,
        "source_provider": provider,
        "source_conversation_id": "conv-harbor-042",
        "source_message_refs": ["msg-1"],
        "capture_mode": "structured_submission",
        "summary": summary,
        "capture_items": [
            {"item_type": "observation", "text": "Postgres 15 vs 16 remains unresolved."},
            {"item_type": "idea", "text": "Keep volume-root discovery out of capture."},
            {"item_type": "action_item", "text": "Inspect conversation-capture list lens."},
            {"item_type": "open_question", "text": "Which project owns this note?"},
        ],
    }


def _seed_capture(
    vault: Path, *, project_id: str = "harbor-api", summary: str = "Harbor note"
) -> dict[str, Any]:
    return capture_conversation(
        vault, _envelope(project_id=project_id, summary=summary)
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(
        ConversationCapturesReadError, match="conversation-captures-vault-missing"
    ):
        build_conversation_captures_read(tmp_path / "absent")


def test_missing_directory_is_unknown_not_clean(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = build_conversation_captures_read(vault)
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["reason_code"] == "DIRECTORY_ABSENT"
    assert report["capture_count"] == 0
    assert report["directory_present"] is False
    assert report["honesty"]["unknown_is_clean"] is False
    assert report["honesty"]["unknown_is_healthy"] is False
    assert report["honesty"]["owner_capability_granted"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["honesty"]["conversation_is_owner_grant"] is False
    text = render_conversation_captures_read_text(report)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "[CLEAN]" not in text


def test_empty_directory_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "generated" / "ops" / "conversation-captures").mkdir(parents=True)
    report = build_conversation_captures_read(vault)
    assert report["status"] == "EMPTY"
    assert report["available"] is True
    assert report["reason_code"] == "DIRECTORY_EMPTY"
    assert report["capture_count"] == 0
    assert report["honesty"]["empty_is_healthy"] is False
    assert report["status"] != "HEALTHY"


def test_present_capture_is_quarantined_visible(tmp_path: Path) -> None:
    vault = _vault_with_projects(tmp_path, "harbor-api")
    seeded = _seed_capture(vault)
    report = build_conversation_captures_read(vault)
    assert report["status"] == "PRESENT"
    assert report["available"] is True
    assert report["capture_count"] == 1
    assert report["captures"][0]["capture_id"] == seeded["capture_id"]
    assert report["captures"][0]["authority"] is False
    assert report["captures"][0]["promoted_to_authority"] is False
    assert report["honesty"]["capture_is_truth_core"] is False
    assert report["honesty"]["lens_is_authority"] is False
    assert report["honesty"]["quarantine_is_authority"] is False


def test_reviewed_capture_is_not_promoted(tmp_path: Path) -> None:
    vault = _vault_with_projects(tmp_path, "harbor-api")
    seeded = _seed_capture(vault)
    set_conversation_review_state(vault, seeded["capture_id"], "reviewed")
    report = build_conversation_captures_read(vault)
    assert report["status"] == "PRESENT"
    assert report["captures"][0]["review_state"] == "reviewed"
    assert report["captures"][0]["authority"] is False
    assert report["captures"][0]["promoted_to_authority"] is False
    assert report["honesty"]["reviewed_is_promoted"] is False
    assert report["honesty"]["owner_capability_granted"] is False


def test_project_scope_hides_sibling(tmp_path: Path) -> None:
    vault = _vault_with_projects(tmp_path, "harbor-api", "portal")
    harbor = _seed_capture(vault, project_id="harbor-api", summary="Harbor")
    portal = _seed_capture(vault, project_id="portal", summary="Portal")
    scoped = build_conversation_captures_read(vault, "harbor-api")
    other = build_conversation_captures_read(vault, "portal")
    assert [row["capture_id"] for row in scoped["captures"]] == [harbor["capture_id"]]
    assert [row["capture_id"] for row in other["captures"]] == [portal["capture_id"]]
    assert portal["capture_id"] not in [
        row["capture_id"] for row in scoped["captures"]
    ]


def test_unrelated_project_is_empty_not_present(tmp_path: Path) -> None:
    vault = _vault_with_projects(tmp_path, "harbor-api", "missing-sibling")
    _seed_capture(vault, project_id="harbor-api")
    report = build_conversation_captures_read(vault, "missing-sibling")
    assert report["status"] == "EMPTY"
    assert report["capture_count"] == 0
    assert report["honesty"]["empty_is_healthy"] is False


def test_unsafe_project_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(
        ConversationCapturesReadError, match="conversation-captures-project-unsafe"
    ):
        build_conversation_captures_read(vault, "../escape")


def test_unreadable_captures_are_unknown_not_empty(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "conversation-captures" / "ccap-bad.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    report = build_conversation_captures_read(vault)
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["reason_code"] == "CAPTURES_UNREADABLE"
    assert report["unreadable_count"] == 1
    assert report["honesty"]["unknown_is_clean"] is False


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = _vault_with_projects(tmp_path, "harbor-api")
    _seed_capture(vault)
    before = _snapshot(vault)
    build_conversation_captures_read(vault)
    build_conversation_captures_read(vault, "harbor-api")
    assert _snapshot(vault) == before


def test_missing_directory_read_does_not_create_files(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    build_conversation_captures_read(vault)
    assert _snapshot(vault) == before
    assert not (vault / "generated" / "ops" / "conversation-captures").exists()


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = _vault_with_projects(tmp_path, "harbor-api")
    _seed_capture(vault)
    first = build_conversation_captures_read(vault, "harbor-api")
    second = build_conversation_captures_read(vault, "harbor-api")
    assert first == second


def test_cross_vault_captures_are_not_imported(tmp_path: Path) -> None:
    left = _vault_with_projects(tmp_path / "left", "harbor-api")
    _seed_capture(left, project_id="harbor-api")
    right = tmp_path / "right"
    right.mkdir()
    report = build_conversation_captures_read(right, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["capture_count"] == 0


def test_session_capture_is_not_listed_as_conversation(tmp_path: Path) -> None:
    vault = _vault_with_projects(tmp_path, "harbor-api")
    capture_session(vault, project_id="harbor-api", summary="session only")
    report = build_conversation_captures_read(vault)
    assert report["status"] == "UNKNOWN"
    assert report["capture_count"] == 0


def test_cli_json_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert (
        main(["conversation-captures", "--vault", str(vault), "--json"]) == EXIT_OK
    )


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(
            [
                "conversation-captures",
                "--vault",
                str(tmp_path / "absent"),
                "--json",
            ]
        )
        == EXIT_ERROR
    )


def test_existing_session_capture_list_unchanged(tmp_path: Path) -> None:
    from project_atlas.cli import build_parser

    help_text = build_parser().format_help()
    assert "conversation-captures" in help_text
    assert "capture" in help_text
    vault = _vault_with_projects(tmp_path, "harbor-api")
    capture_session(vault, project_id="harbor-api", summary="session memory")
    _seed_capture(vault)
    assert main(["capture", "list", "--vault", str(vault), "--json"]) == EXIT_OK


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.conversation.captures.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.conversation.captures.write" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.conversation.captures.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["unknown_is_clean"] is False
    assert result["honesty"]["owner_capability_granted"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {
                    "tool": "atlas.conversation.captures.read",
                    "args": {"project": "x"},
                }
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.conversation.captures.write", "write": True}
            ),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(
            vault, "atlas.conversation.captures.read", operator=bare
        )


def test_api_conversation_captures_route(tmp_path: Path) -> None:
    vault = _vault_with_projects(tmp_path, "harbor-api")
    _seed_capture(vault)
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
        assert meta["conversation_captures_live"] is True
        with urlopen(
            Request(
                f"http://{host}:{port}/v1/conversation-captures?project=harbor-api",
                headers=auth,
            ),
            timeout=2,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "PRESENT"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
        assert body["honesty"]["reviewed_is_promoted"] is False
    finally:
        server.shutdown()


def test_api_conversation_captures_list_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/conversation-captures",
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
    assert "AS-CODER-ALPHA-CONVERSATION-CAPTURES-READ-001" not in authentic
    assert "AS-CODER-ALPHA-CONVERSATION-CAPTURES-READ-001" not in reconciler
    assert "conversation_captures_read" not in reconciler


def test_web_demo_stub_does_not_fabricate_empty_or_healthy() -> None:
    """Demo hook must stay UNKNOWN — no invented EMPTY/HEALTHY/PRESENT rows."""
    hook = (
        Path(__file__).resolve().parents[2]
        / "apps/web/src/hooks/useConversationCaptures.ts"
    ).read_text(encoding="utf-8")
    assert 'status: "UNKNOWN"' in hook
    assert 'reason_code: "DEMO_STUB_UNKNOWN"' in hook
    assert "available: false" in hook
    assert "demo_isolated: true" in hook
    assert 'status: "EMPTY"' not in hook
    assert 'status: "HEALTHY"' not in hook
    assert 'status: "PRESENT"' not in hook
    assert "OWNER_CAPABILITY_GRANTED" not in hook
    assert "owner_capability_granted: false" in hook
