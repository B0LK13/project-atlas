"""P1-B — Ledger read integrity (D-196)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.events import normalize_engineering_event
from project_atlas.atlas3.ledger import append_event, list_events, query_events


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _ledger_path(vault: Path) -> Path:
    return vault / "generated" / "ops" / "atlas3" / "ledger" / "harbor-api.jsonl"


def _read_ledger_rows(vault: Path) -> list[dict]:
    path = _ledger_path(vault)
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_foreign_project_row_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        event_type="TEST_PASSED",
        source_plane="engineering",
        summary="ok",
    )
    path = _ledger_path(vault)
    foreign = dict(_read_ledger_rows(vault)[0])
    foreign["project_id"] = "other-api"
    path.write_text(
        path.read_text(encoding="utf-8") + json.dumps(foreign, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(Atlas3Error) as exc:
        list_events(vault, "harbor-api")
    assert exc.value.code == "PROJECT_MISMATCH"


def test_event_id_collision_altered_object_refs_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        event_type="COMMIT_CREATED",
        source_plane="engineering",
        summary="first",
        object_refs=["commit:aaa"],
    )
    path = _ledger_path(vault)
    first = _read_ledger_rows(vault)[0]
    tampered = normalize_engineering_event(
        project_id="harbor-api",
        event_type="COMMIT_CREATED",
        source_plane="engineering",
        summary="first",
        object_refs=["commit:bbb"],
    )
    tampered["event_id"] = first["event_id"]
    path.write_text(
        path.read_text(encoding="utf-8") + json.dumps(tampered, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(Atlas3Error) as exc:
        query_events(vault, project_id="harbor-api")
    assert exc.value.code in {"EVENT_ID_COLLISION", "CONTENT_HASH_MISMATCH"}


def test_event_id_collision_altered_project_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        event_type="TEST_PASSED",
        source_plane="engineering",
        summary="scoped",
    )
    path = _ledger_path(vault)
    first = _read_ledger_rows(vault)[0]
    foreign = normalize_engineering_event(
        project_id="other-api",
        event_type="TEST_PASSED",
        source_plane="engineering",
        summary="scoped",
    )
    foreign["event_id"] = first["event_id"]
    path.write_text(
        path.read_text(encoding="utf-8") + json.dumps(foreign, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(Atlas3Error) as exc:
        list_events(vault, "harbor-api")
    assert exc.value.code in {"PROJECT_MISMATCH", "CONTENT_HASH_MISMATCH", "EVENT_ID_COLLISION"}


def test_hash_mismatch_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    event = normalize_engineering_event(
        project_id="harbor-api",
        event_type="BUILD_FINISHED",
        source_plane="engineering",
        summary="build ok",
    )
    event["content_hash"] = "sha256:" + "c" * 64
    path = _ledger_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(Atlas3Error) as exc:
        query_events(vault, project_id="harbor-api")
    assert exc.value.code == "CONTENT_HASH_MISMATCH"


def test_list_and_query_share_validation(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        event_type="AGENT_FINISHED",
        source_plane="engineering",
        summary="done",
    )
    path = _ledger_path(vault)
    path.write_text(path.read_text(encoding="utf-8") + "broken\n", encoding="utf-8")
    with pytest.raises(Atlas3Error):
        list_events(vault, "harbor-api")
    with pytest.raises(Atlas3Error):
        query_events(vault, project_id="harbor-api")


def test_event_id_collision_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        event_type="TEST_FAILED",
        source_plane="engineering",
        summary="first",
    )
    path = _ledger_path(vault)
    first = _read_ledger_rows(vault)[0]
    tampered = normalize_engineering_event(
        project_id="harbor-api",
        event_type="TEST_FAILED",
        source_plane="engineering",
        summary="altered payload",
    )
    tampered["event_id"] = first["event_id"]
    path.write_text(
        path.read_text(encoding="utf-8") + json.dumps(tampered, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(Atlas3Error) as exc:
        query_events(vault, project_id="harbor-api")
    # Stolen event_id on a different payload fails the hash binding first.
    assert exc.value.code in {"EVENT_ID_COLLISION", "CONTENT_HASH_MISMATCH"}


def test_malformed_json_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        event_type="BUILD_STARTED",
        source_plane="engineering",
        summary="build",
    )
    path = _ledger_path(vault)
    path.write_text(path.read_text(encoding="utf-8") + "not-json\n", encoding="utf-8")
    with pytest.raises(Atlas3Error) as exc:
        list_events(vault, "harbor-api")
    assert exc.value.code == "LEDGER_CORRUPT"


def test_wrong_schema_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    event = normalize_engineering_event(
        project_id="harbor-api",
        kind="failure",
        source_plane="engineering",
        summary="x",
    )
    path = _ledger_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    bad = dict(event)
    bad["schema"] = "wrong.schema.v9"
    path.write_text(json.dumps(bad, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(Atlas3Error) as exc:
        list_events(vault, "harbor-api")
    assert exc.value.code == "LEDGER_SCHEMA_INVALID"


def test_mixed_valid_and_corrupt_no_partial_results(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    good = normalize_engineering_event(
        project_id="harbor-api",
        kind="test",
        source_plane="engineering",
        summary="valid",
    )
    path = _ledger_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(good, sort_keys=True) + "\n" + "broken-line\n",
        encoding="utf-8",
    )
    with pytest.raises(Atlas3Error):
        list_events(vault, "harbor-api")


def test_forged_event_id_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    event = normalize_engineering_event(
        project_id="harbor-api",
        event_type="TEST_PASSED",
        source_plane="engineering",
        summary="ok",
    )
    event["event_id"] = "a3ev-FORGEDIDENTIFIER"
    path = _ledger_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(Atlas3Error) as exc:
        list_events(vault, "harbor-api")
    assert exc.value.code == "CONTENT_HASH_MISMATCH"


def test_identical_replay_collapsed_on_read(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        event_type="AGENT_STARTED",
        source_plane="engineering",
        summary="agent boot",
    )
    path = _ledger_path(vault)
    event = _read_ledger_rows(vault)[0]
    path.write_text(
        path.read_text(encoding="utf-8") + json.dumps(event, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rows = list_events(vault, "harbor-api")
    assert len(rows) == 1
