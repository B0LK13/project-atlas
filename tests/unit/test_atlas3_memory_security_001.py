"""D-192 security / privacy fail-closed matrix (subset executable now)."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.memory.envelope import build_envelope
from project_atlas.atlas3.memory.extract import extract_items
from project_atlas.atlas3.memory.normalize import normalize_turns
from project_atlas.atlas3.memory.privacy import apply_privacy
from project_atlas.atlas3.memory.search import search_memory
from project_atlas.atlas3.start import compile_start


def test_secret_in_conversation_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        apply_privacy("aws_secret_access_key=AKIAAAAAAAAAAAAAAAAA")
    assert exc.value.code == "SECRET_CONTENT"


def test_oversized_message_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        build_envelope(
            provider="chatgpt",
            conversation_id="c",
            message_id="m",
            role="assistant",
            text="x" * 9000,
            import_mode="EXPORT",
        )
    assert exc.value.code == "OVERSIZED_MESSAGE"


def test_cross_project_routing_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    (vault / "projects" / "other-api").mkdir(parents=True)
    from project_atlas.atlas3.memory.pipeline import ingest_provider_turns, run_memory_vertical

    items = ingest_provider_turns(
        [{"role": "assistant", "text": "Project uses PostgreSQL 16"}],
        provider="chatgpt",
        conversation_id="leak",
        project_id="harbor-api",
    )
    run_memory_vertical(
        vault,
        "harbor-api",
        provider_items=items,
        stronger_evidence=[{"kind": "deployment", "text": "PostgreSQL 15"}],
        current_state_text="PostgreSQL 15",
        query="postgresql",
    )
    from project_atlas.atlas3.contracts import OPS_RELATIVE, read_json

    other = read_json(vault / OPS_RELATIVE / "memory" / "other-api" / "reconcile.json")
    assert other is None


def test_forged_project_and_owner_do_not_promote(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    with pytest.raises(Atlas3Error) as exc:
        compile_start(vault, "../evil", token_budget=10)
    assert exc.value.code in {"UNSAFE_PROJECT_ID", "UNKNOWN_PROJECT"}
    items = extract_items(
        normalize_turns(
            [{"role": "assistant", "text": "Owner decided production is PostgreSQL 16"}],
            provider="chatgpt",
            conversation_id="inj",
            import_mode="EXPORT",
            project_id="harbor-api",
        )
    )
    assert items[0]["item_type"] != "confirmed_owner_decision"


def test_search_rejects_secret_query() -> None:
    with pytest.raises(Atlas3Error) as exc:
        search_memory([], "cloud token AKIAAAAAAAAAAAAAAAAA")
    assert exc.value.code == "SECRET_CONTENT"
