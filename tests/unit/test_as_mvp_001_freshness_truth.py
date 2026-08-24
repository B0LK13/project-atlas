"""AS-MVP-001-FRESHNESS-TRUTH-001 — epoch mtimes are unknown, not stale."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from project_atlas.portfolio import is_untrusted_mtime, stale_knowledge

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
