"""AS-CODER-ALPHA-INBOX-LIST-001 — read-only project-scoped inbox list.

INBOX != AUTHORITY. No implicit portfolio-all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.cli import main
from project_atlas.knowledge_inbox import (
    KnowledgeInboxError,
    build_knowledge_inbox_receipt,
    list_inbox_items,
)
from project_atlas.secrets import scan_text


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _capture(
    vault: Path,
    *,
    capture_id: str,
    project_id: str,
    summary: str,
    review_state: str = "captured",
    items: list[dict[str, str]] | None = None,
) -> None:
    inbox_status = {
        "captured": "quarantined",
        "reviewed": "accepted-review",
        "rejected": "rejected",
    }[review_state]
    _write(
        vault / "generated" / "ops" / "conversation-captures" / f"{capture_id}.json",
        {
            "capture_id": capture_id,
            "project_id": project_id,
            "summary": summary,
            "review_state": review_state,
            "capture_items": items or [{"item_type": "observation", "text": summary}],
            "inbox": {"status": inbox_status, "promoted_to_authority": False},
        },
    )
    build_knowledge_inbox_receipt(
        vault,
        record_id=capture_id,
        status=inbox_status,
        item_count=1,
    )


def test_list_requires_explicit_project(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(KnowledgeInboxError) as exc:
        list_inbox_items(vault, project_id="")
    assert exc.value.code == "UNSUPPORTED_SCOPE"


def test_list_rejects_long_and_path_shaped_project(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(KnowledgeInboxError) as exc:
        list_inbox_items(vault, project_id="a" * 80)
    assert exc.value.code == "MALFORMED_INPUT"
    with pytest.raises(KnowledgeInboxError) as exc:
        list_inbox_items(vault, project_id="../harbor-api")
    assert exc.value.code == "MALFORMED_INPUT"
    with pytest.raises(KnowledgeInboxError) as exc:
        list_inbox_items(vault, project_id="Harbor_API")
    assert exc.value.code == "MALFORMED_INPUT"


def test_list_empty_is_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = list_inbox_items(vault, project_id="harbor-api")
    assert report["items"] == []
    assert report["unknown"] == "UNKNOWN (no inbox items for project)"
    assert report["promoted_to_authority"] is False


def test_list_is_project_scoped_and_deterministic(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _capture(vault, capture_id="ccap-b", project_id="harbor-api", summary="later-id")
    _capture(vault, capture_id="ccap-a", project_id="harbor-api", summary="earlier-id")
    _capture(vault, capture_id="ccap-z", project_id="portal-app", summary="other-project")
    report = list_inbox_items(vault, project_id="harbor-api")
    ids = [item["receipt_id"] for item in report["items"]]
    assert ids == ["ccap-a", "ccap-b"]
    assert all(item["project_id"] == "harbor-api" for item in report["items"])
    assert all(item["promoted_to_authority"] is False for item in report["items"])
    leaked = list_inbox_items(vault, project_id="portal-app")
    assert [item["receipt_id"] for item in leaked["items"]] == ["ccap-z"]


def test_list_status_filter_and_limit(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _capture(vault, capture_id="ccap-q", project_id="harbor-api", summary="q")
    _capture(
        vault,
        capture_id="ccap-r",
        project_id="harbor-api",
        summary="r",
        review_state="reviewed",
    )
    filtered = list_inbox_items(vault, project_id="harbor-api", status="accepted-review")
    assert [item["receipt_id"] for item in filtered["items"]] == ["ccap-r"]
    limited = list_inbox_items(vault, project_id="harbor-api", limit=1)
    assert limited["count"] == 1
    assert limited["items"][0]["receipt_id"] == "ccap-q"
    with pytest.raises(KnowledgeInboxError) as exc:
        list_inbox_items(vault, project_id="harbor-api", limit=0)
    assert exc.value.code == "MALFORMED_INPUT"


def test_list_skips_orphan_receipts_and_promote_tamper(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    build_knowledge_inbox_receipt(vault, record_id="orphan-1", item_count=1)
    _capture(vault, capture_id="ccap-ok", project_id="harbor-api", summary="ok")
    tampered = vault / "generated" / "ops" / "inbox" / "ccap-ok.json"
    payload = json.loads(tampered.read_text(encoding="utf-8"))
    payload["promoted_to_authority"] = True
    tampered.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    # Capture still lists via inbox metadata; receipt promote-true is ignored.
    report = list_inbox_items(vault, project_id="harbor-api")
    assert [item["receipt_id"] for item in report["items"]] == ["ccap-ok"]
    assert report["items"][0]["promoted_to_authority"] is False
    assert "orphan-1" not in [item["receipt_id"] for item in report["items"]]


def test_list_redacts_secret_shaped_summary(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    secret = "AKIA" + "ABCDEFGHIJKLMNOP"
    assert scan_text(secret)
    _capture(vault, capture_id="ccap-s", project_id="harbor-api", summary=secret)
    report = list_inbox_items(vault, project_id="harbor-api")
    assert report["items"][0]["summary"] == "[redacted: secret-shaped value]"
    assert secret not in json.dumps(report)


def test_cli_inbox_list_json_and_human(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _capture(vault, capture_id="ccap-cli", project_id="harbor-api", summary="cli-row")
    assert (
        main(
            [
                "inbox",
                "list",
                "--vault",
                str(vault),
                "--project",
                "harbor-api",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["promoted_to_authority"] is False
    assert payload["items"][0]["receipt_id"] == "ccap-cli"

    assert (
        main(
            [
                "inbox",
                "list",
                "--vault",
                str(vault),
                "--project",
                "harbor-api",
            ]
        )
        == 0
    )
    human = capsys.readouterr().out
    assert "INBOX != AUTHORITY" in human
    assert "ccap-cli" in human


def test_cli_inbox_list_rejects_implicit_all_and_long_token(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    code = main(["inbox", "list", "--vault", str(vault), "--json"])
    assert code == 1
    err = json.loads(capsys.readouterr().out)
    assert err["error"] == "UNSUPPORTED_SCOPE"

    code = main(
        [
            "inbox",
            "list",
            "--vault",
            str(vault),
            "--project",
            "x" * 80,
            "--json",
        ]
    )
    assert code == 1
    err = json.loads(capsys.readouterr().out)
    assert err["error"] == "MALFORMED_INPUT"
    assert err["promoted_to_authority"] is False
