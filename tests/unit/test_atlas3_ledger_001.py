"""AT3-014 universal event ledger."""

from __future__ import annotations

from pathlib import Path

from project_atlas.atlas3.events import normalize_engineering_event
from project_atlas.atlas3.ledger import append_event, list_events


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def test_append_replay_and_no_ops_events_write(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    event = normalize_engineering_event(
        project_id="harbor-api",
        kind="failure",
        source_plane="engineering",
        summary="CI failed on kdiff",
    )
    first = append_event(vault, "harbor-api", event)
    second = append_event(vault, "harbor-api", event)
    assert first["idempotency"] == "appended"
    assert second["idempotency"] == "replay"
    assert len(list_events(vault, "harbor-api")) == 1
    assert not (vault / "generated" / "ops" / "events").exists()
    assert (vault / "generated" / "ops" / "atlas3" / "ledger" / "harbor-api.jsonl").is_file()
