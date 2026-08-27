"""AS-MVP-001-FRESHNESS-TRUTH-001 — epoch mtimes are unknown, not stale."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from project_atlas.portfolio import (
    DEFAULT_STALE_DAYS,
    is_untrusted_mtime,
    stale_knowledge,
)

REFERENCE = datetime(2026, 8, 1, tzinfo=UTC)


def _write_manifest(vault: Path, sources: list[dict[str, object]]) -> None:
    path = vault / "sources" / "manifests" / "source-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 1, "sources": sources}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def test_unix_epoch_is_untrusted_mtime() -> None:
    assert is_untrusted_mtime(datetime(1970, 1, 1, tzinfo=UTC))
    assert not is_untrusted_mtime(datetime(2024, 1, 1, tzinfo=UTC))


def test_epoch_mtime_is_not_reported_stale(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        [
            {
                "source_id": "src-epoch",
                "path": "docs/copied.md",
                "likely_project": "nebula",
                "modified_at": "1970-01-01T00:00:00+00:00",
            },
            {
                "source_id": "src-fresh",
                "path": "docs/current.md",
                "likely_project": "nebula",
                "modified_at": "2026-07-01T00:00:00+00:00",
            },
        ],
    )
    report = stale_knowledge(vault, reference_date=REFERENCE, stale_after_days=180)
    nebula = report["projects"].get("nebula", {"stale_count": 0, "sources": []})
    assert nebula["stale_count"] == 0
    ids = {item["source_id"] for item in nebula["sources"]}
    assert "src-epoch" not in ids
    assert "src-fresh" in ids


def test_threshold_boundary_is_exact(tmp_path: Path) -> None:
    """``stale_after_days`` is an inclusive boundary: a source exactly that
    many days old is stale, one day younger is fresh. Pinned against an
    injected reference date, so the boundary cannot be silently widened by
    a later tolerance change or drift into a different answer over time.
    """
    vault = tmp_path / "vault"
    threshold = DEFAULT_STALE_DAYS
    _write_manifest(
        vault,
        [
            {
                "source_id": "src-at-threshold",
                "path": "docs/at.md",
                "likely_project": "nebula",
                "modified_at": (REFERENCE - timedelta(days=threshold)).isoformat(),
            },
            {
                "source_id": "src-just-under",
                "path": "docs/under.md",
                "likely_project": "nebula",
                "modified_at": (REFERENCE - timedelta(days=threshold - 1)).isoformat(),
            },
        ],
    )
    report = stale_knowledge(vault, reference_date=REFERENCE, stale_after_days=threshold)
    freshness = {
        item["source_id"]: item["freshness"] for item in report["projects"]["nebula"]["sources"]
    }
    assert freshness == {"src-at-threshold": "stale", "src-just-under": "fresh"}
    assert report["projects"]["nebula"]["stale_count"] == 1


def test_offset_timestamps_compare_as_instants(tmp_path: Path) -> None:
    """A non-UTC offset timestamp is compared as the instant it denotes, so
    the same moment expressed in two timezones yields the same freshness."""
    vault = tmp_path / "vault"
    instant = REFERENCE - timedelta(days=DEFAULT_STALE_DAYS + 5)
    _write_manifest(
        vault,
        [
            {
                "source_id": "src-utc",
                "path": "docs/utc.md",
                "likely_project": "nebula",
                "modified_at": instant.isoformat(),
            },
            {
                "source_id": "src-offset",
                "path": "docs/offset.md",
                "likely_project": "nebula",
                "modified_at": instant.astimezone(timezone(timedelta(hours=9))).isoformat(),
            },
        ],
    )
    report = stale_knowledge(vault, reference_date=REFERENCE, stale_after_days=DEFAULT_STALE_DAYS)
    freshness = {
        item["source_id"]: item["freshness"] for item in report["projects"]["nebula"]["sources"]
    }
    assert freshness == {"src-utc": "stale", "src-offset": "stale"}
