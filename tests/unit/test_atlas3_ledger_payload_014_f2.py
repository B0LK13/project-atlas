"""AT3-014-F2 — self-consistent non-object payload is invalid schema."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.events import normalize_engineering_event, verify_engineering_event
from project_atlas.atlas3.ledger import append_event, ledger_status, list_events
from project_atlas.atlas3.pulse import compile_pulse


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _ledger_path(vault: Path) -> Path:
    return vault / "generated" / "ops" / "atlas3" / "ledger" / "harbor-api.jsonl"


def _rebind(event: dict[str, object], *, payload: object) -> dict[str, object]:
    event["payload"] = payload
    body = {key: value for key, value in event.items() if key not in {"event_id", "content_hash"}}
    digest = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    event["content_hash"] = digest
    event["event_id"] = "a3ev-" + digest[7:23]
    return event


def _write_rebound(vault: Path, payload: object) -> None:
    event = normalize_engineering_event(
        project_id="harbor-api",
        event_type="TEST_PASSED",
        source_plane="engineering",
        summary="ok",
    )
    _rebind(event, payload=payload)
    path = _ledger_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")


def test_self_consistent_string_payload_fails_verify() -> None:
    event = normalize_engineering_event(
        project_id="harbor-api",
        event_type="TEST_PASSED",
        source_plane="engineering",
        summary="ok",
    )
    _rebind(event, payload="not-an-object")
    with pytest.raises(Atlas3Error) as exc:
        verify_engineering_event(event, expected_project_id="harbor-api")
    assert exc.value.code == "LEDGER_SCHEMA_INVALID"


@pytest.mark.parametrize("payload", ["not-an-object", ["stale"], 1, True])
def test_self_consistent_non_object_payload_fail_closed(tmp_path: Path, payload: object) -> None:
    vault = _vault(tmp_path)
    _write_rebound(vault, payload)
    with pytest.raises(Atlas3Error) as exc:
        list_events(vault, "harbor-api")
    assert exc.value.code == "LEDGER_SCHEMA_INVALID"


def test_mixed_valid_and_non_object_payload_no_partial_results(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    good = normalize_engineering_event(
        project_id="harbor-api",
        event_type="TEST_PASSED",
        source_plane="engineering",
        summary="valid",
    )
    bad = _rebind(
        normalize_engineering_event(
            project_id="harbor-api",
            event_type="TEST_FAILED",
            source_plane="engineering",
            summary="corrupt payload",
        ),
        payload="not-an-object",
    )
    path = _ledger_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(good, sort_keys=True) + "\n" + json.dumps(bad, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(Atlas3Error) as exc:
        list_events(vault, "harbor-api")
    assert exc.value.code == "LEDGER_SCHEMA_INVALID"
    with pytest.raises(Atlas3Error):
        ledger_status(vault, "harbor-api")


def test_pulse_does_not_attributeerror_on_string_payload(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_rebound(vault, "not-an-object")
    with pytest.raises(Atlas3Error) as exc:
        compile_pulse(vault, "harbor-api")
    assert exc.value.code == "LEDGER_SCHEMA_INVALID"


def test_empty_object_payload_still_reads(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        event_type="TEST_PASSED",
        source_plane="engineering",
        summary="ok",
        payload={},
    )
    rows = list_events(vault, "harbor-api")
    assert len(rows) == 1
    assert rows[0]["payload"] == {}
