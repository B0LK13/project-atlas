"""AT3-045 — provider identity + session lineage."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.memory.lineage import PACKAGE_ID, build_session_lineage


def _env(
    *,
    conversation_id: str = "c1",
    provider: str = "chatgpt",
    message_id: str = "m1",
    content_hash: str = "sha256:aaa",
    project_id: str = "harbor-api",
) -> dict[str, str]:
    return {
        "conversation_id": conversation_id,
        "provider": provider,
        "message_id": message_id,
        "content_hash": content_hash,
        "project_id": project_id,
    }


def test_missing_project_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        build_session_lineage([], requested_project_id="")
    assert exc.value.code == "PROJECT_REQUIRED"


def test_cross_project_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        build_session_lineage(
            [_env(project_id="foreign")],
            requested_project_id="harbor-api",
        )
    assert exc.value.code == "CROSS_PROJECT"


def test_provider_spoof_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        build_session_lineage(
            [
                _env(provider="chatgpt", message_id="m1"),
                _env(provider="claude", message_id="m2", content_hash="sha256:bbb"),
            ],
            requested_project_id="harbor-api",
        )
    assert exc.value.code == "PROVIDER_SPOOF"


def test_altered_payload_same_message_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        build_session_lineage(
            [
                _env(content_hash="sha256:aaa"),
                _env(content_hash="sha256:bbb"),
            ],
            requested_project_id="harbor-api",
        )
    assert exc.value.code == "LINEAGE_HASH_MISMATCH"


def test_incomplete_identity_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        build_session_lineage(
            [{"project_id": "harbor-api", "conversation_id": "c1", "provider": "chatgpt"}],
            requested_project_id="harbor-api",
        )
    assert exc.value.code == "LINEAGE_IDENTITY_INCOMPLETE"


def test_stable_session_lineage() -> None:
    report = build_session_lineage(
        [
            _env(message_id="m1", content_hash="sha256:aaa"),
            _env(message_id="m2", content_hash="sha256:bbb"),
        ],
        requested_project_id="harbor-api",
    )
    assert report["package_id"] == PACKAGE_ID
    assert report["session_count"] == 1
    assert report["message_count"] == 2
    assert report["sessions"][0]["provider"] == "chatgpt"
    assert report["honesty"]["metadata_is_authority"] is False
    assert report["honesty"]["write_applied"] is False
    assert "PROVIDER SPOOFING FAILS CLOSED" in report["truth_boundary"]


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/memory/lineage.py").read_text(encoding="utf-8")
    for name in (
        "knowledge_compiler",
        "from project_atlas.ingestion",
        "write_json_atomic",
        "write_text(",
        "ask_atlas_2(",
    ):
        assert name not in source
