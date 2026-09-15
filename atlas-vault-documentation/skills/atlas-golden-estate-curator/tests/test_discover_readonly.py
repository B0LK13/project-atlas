"""Fixture estate discovery is read-only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from curator import CuratorError, curate  # noqa: E402
from estate import fingerprint  # noqa: E402


def test_fixture_estate_is_read_only(tmp_path: Path, fixture_estate: Path) -> None:
    source = fixture_estate
    before = fingerprint(source)
    report = curate(
        source,
        phase="RECOMMEND",
        output=tmp_path / "report.json",
    )
    after = fingerprint(source)
    assert before == after
    assert report["source_mutations"] == 0
    assert report["files_moved"] == 0
    assert report["files_deleted"] == 0
    kinds = {item["kind"] for item in report["inventory"]}
    assert "git" in kinds
    assert "non-git" in kinds
    assert "nested-repo" in kinds
    names = {item["name"] for item in report["inventory"]}
    assert "healthy-git" in names
    assert "non-git-folder" in names
    assert "dirty-worktree" in names
    assert "missing-readme" in names
    assert "stale-docs" in names
    assert "fake-secret" in names
    assert report["recommendation"]["copy_authorized"] is False
    payload = json.dumps(report)
    assert "NOT_A_REAL_SECRET_VALUE" not in payload
    assert (tmp_path / "report.json").is_file()
    golden = report["recommendation"]["recommended_golden_set"]
    assert any(path.endswith("healthy-git") or path == "healthy-git" for path in golden)


def test_output_inside_source_fails(tmp_path: Path, fixture_estate: Path) -> None:
    source = fixture_estate
    with pytest.raises(CuratorError) as exc:
        curate(source, output=source / "inside.json")
    assert exc.value.code == "OUTPUT_INSIDE_SOURCE"
