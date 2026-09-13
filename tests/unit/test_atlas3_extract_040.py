"""AT3-040 — Deterministic conversation knowledge extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import ITEM_TYPES, Atlas3Error
from project_atlas.atlas3.memory.extract import (
    PACKAGE_ID,
    extract_capability,
    extract_items,
    reject_forged_owner_decision,
)


def test_capability_is_non_canonical() -> None:
    cap = extract_capability()
    assert cap["package"] == PACKAGE_ID
    assert cap["llm_assisted"] is False
    assert cap["authority"] == "NON_CANONICAL"
    assert cap["auto_promote_to_truth_core"] is False
    assert set(cap["item_types"]) == set(ITEM_TYPES)


def test_forged_owner_stays_proposed() -> None:
    forged = reject_forged_owner_decision("Owner decided to rollback to PostgreSQL 15")
    assert forged["item_type"] == "proposed_decision"
    assert forged["forged_owner_blocked"] is True
    items = extract_items(
        [
            {
                "role": "assistant",
                "content_reference": "Owner decided to rollback to PostgreSQL 15",
                "provider": "chatgpt",
                "conversation_id": "c1",
                "message_id": "m1",
                "content_hash": "sha256:x",
                "project_id": "harbor-api",
            }
        ]
    )
    assert items[0]["item_type"] == "proposed_decision"
    assert items[0]["authority"] == "NON_CANONICAL"
    assert "owner_origin" not in items[0]
    assert items[0].get("promoted_to_truth_core") is not True


def test_confirmed_owner_requires_origin() -> None:
    origin = {
        "evidence_kind": "explicit_owner_statement",
        "origin": "owner",
        "statement": "Keep PostgreSQL 15",
    }
    items = extract_items(
        [
            {
                "role": "owner",
                "content_reference": "Keep PostgreSQL 15",
                "provider": "chatgpt",
                "conversation_id": "c1",
                "message_id": "m1",
                "content_hash": "sha256:x",
                "project_id": "harbor-api",
            }
        ],
        owner_origin=origin,
    )
    assert items[0]["item_type"] == "confirmed_owner_decision"
    assert items[0]["owner_origin"]["origin"] == "owner"


def test_mixed_valid_and_corrupt_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        extract_items(
            [{"role": "user", "content_reference": "ok"}, "corrupt"]  # type: ignore[list-item]
        )
    assert exc.value.code == "EXTRACT_INVALID"


def test_non_list_envelopes_fail_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        extract_items({"role": "user", "content_reference": "ok"})  # type: ignore[arg-type]
    assert exc.value.code == "EXTRACT_INVALID"


def test_secret_shaped_text_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        extract_items(
            [
                {
                    "role": "user",
                    "content_reference": "aws_secret_access_key=AKIAAAAAAAAAAAAAAAAA",
                }
            ]
        )
    assert exc.value.code == "SECRET_CONTENT"


def test_planned_claim_is_not_current_state() -> None:
    items = extract_items(
        [
            {
                "role": "assistant",
                "content_reference": "Migration to PostgreSQL 16 remains planned",
                "provider": "gemini",
                "conversation_id": "c1",
                "message_id": "m1",
                "content_hash": "sha256:a",
                "project_id": "harbor-api",
            }
        ]
    )
    assert items[0]["item_type"] == "proposed_decision"
    assert items[0]["item_type"] != "claim_candidate"


def test_planned_should_claim_is_next_step() -> None:
    items = extract_items(
        [
            {
                "role": "assistant",
                "content_reference": "we should migrate production postgres later",
                "provider": "cursor",
                "conversation_id": "c1",
                "message_id": "m2",
                "content_hash": "sha256:b",
                "project_id": "harbor-api",
            }
        ]
    )
    assert items[0]["item_type"] == "next_step"
    assert items[0]["item_type"] != "claim_candidate"


def test_present_tense_after_is_not_planned_intent() -> None:
    items = extract_items(
        [
            {
                "role": "assistant",
                "content_reference": (
                    "production uses PostgreSQL 15 after the extension replacement"
                ),
                "provider": "chatgpt",
                "conversation_id": "c1",
                "message_id": "m4",
                "content_hash": "sha256:d",
                "project_id": "harbor-api",
            }
        ]
    )
    assert items[0]["item_type"] == "claim_candidate"


def test_current_claim_without_plan_stays_claim() -> None:
    items = extract_items(
        [
            {
                "role": "assistant",
                "content_reference": "production uses PostgreSQL 15",
                "provider": "chatgpt",
                "conversation_id": "c1",
                "message_id": "m3",
                "content_hash": "sha256:c",
                "project_id": "harbor-api",
            }
        ]
    )
    assert items[0]["item_type"] == "claim_candidate"


def test_module_does_not_touch_2x_bridges() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/memory/extract.py").read_text(encoding="utf-8")
    for name in (
        "from project_atlas.chatgpt_bridge",
        "from project_atlas.knowledge_compiler",
        "from project_atlas.ingestion",
        "write_text(",
    ):
        assert name not in source
