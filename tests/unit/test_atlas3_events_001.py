"""AT3-003 engineering event model."""

from __future__ import annotations

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.events import ingest_existing_agent_event, normalize_engineering_event


def test_normalize_is_deterministic() -> None:
    first = normalize_engineering_event(
        project_id="harbor-api",
        kind="commit",
        source_plane="engineering",
        summary="Landed freshness fix",
        subject_id="abc123",
    )
    second = normalize_engineering_event(
        project_id="harbor-api",
        kind="commit",
        source_plane="engineering",
        summary="Landed freshness fix",
        subject_id="abc123",
    )
    assert first["event_id"] == second["event_id"]
    assert first["content_hash"].startswith("sha256:")
    assert first["honesty"]["full_live_demo_ready"] is False


def test_unknown_kind_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        normalize_engineering_event(
            project_id="harbor-api",
            kind="magic",
            source_plane="engineering",
            summary="nope",
        )
    assert exc.value.code == "UNKNOWN_EVENT_KIND"


def test_wrap_agent_event_does_not_mutate_source() -> None:
    raw = {"event_type": "decision", "event_id": "evt-1", "summary": "Keep Postgres 15"}
    wrapped = ingest_existing_agent_event(raw, project_id="harbor-api")
    assert wrapped["kind"] == "decision"
    assert wrapped["source_plane"] == "agent_event"
    assert raw["event_type"] == "decision"
