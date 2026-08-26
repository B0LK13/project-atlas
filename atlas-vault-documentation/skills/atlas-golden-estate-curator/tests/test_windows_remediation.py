"""GE-WIN-001 / GE-WIN-002 synthetic remediations.

Cloud must not require a real D:\\ drive. These tests inject Windows-style
path strings and OSError/WinError 1920 failures at multiple traversal stages.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from curator import (  # noqa: E402
    CANONICAL_REPORT_PATH_SEPARATOR,
    EXCLUSION_REASONS,
    INACCESSIBLE_REASON,
    CuratorError,
    canonicalize_report_path,
    curate,
    estimate_disk,
    report_relpath,
)
from estate import _init_repo, build_name_duplicate_estate, fingerprint  # noqa: E402

WIN1920 = (1920, "The file cannot be accessed by the system")


def _win1920(path: Path) -> OSError:
    return OSError(WIN1920[0], WIN1920[1], str(path))


def _commit(project: Path, message: str, *paths: str) -> None:
    add = ["git", "-C", str(project), "add"]
    if paths:
        add.extend(["-f", *paths])
    else:
        add.append(".")
    subprocess.run(
        add,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(project), "commit", "-m", message],
        check=True,
        capture_output=True,
        text=True,
    )


def _relative_fields(report: dict) -> list[str]:
    values: list[str] = []
    for item in report["inventory"]:
        values.append(str(item["path"]))
        if item.get("duplicate_of"):
            values.append(str(item["duplicate_of"]))
    for item in report["qualification"]:
        values.append(str(item["path"]))
    for item in report["candidate_table"]:
        values.append(str(item["path"]))
    for item in report["exclusions"]:
        values.append(str(item["path"]))
    values.extend(str(item) for item in report["generated_directories"])
    rec = report["recommendation"]
    values.extend(str(item) for item in rec["recommended_golden_set"])
    values.extend(str(item) for item in rec["recommended_challenge_set"])
    values.extend(str(item) for item in rec["security_exclusions"])
    return values


def _assert_posix_relative(report: dict) -> None:
    for value in _relative_fields(report):
        assert "\\" not in value, value
        assert CANONICAL_REPORT_PATH_SEPARATOR in value or "/" not in value or value in {
            ".",
            "",
        } or value == canonicalize_report_path(value)


def test_canonicalize_windows_report_identity() -> None:
    assert canonicalize_report_path(r"group-a\widget") == "group-a/widget"
    assert canonicalize_report_path("group-a/widget") == "group-a/widget"
    assert canonicalize_report_path(r"group-a\\widget") == "group-a/widget"


def test_report_relpath_is_posix(tmp_path: Path) -> None:
    root = tmp_path / "estate"
    widget = root / "group-a" / "widget"
    widget.mkdir(parents=True)
    assert report_relpath(widget, root) == "group-a/widget"
    assert "\\" not in report_relpath(widget, root)


def test_ge_win_001_persisted_relative_paths_are_posix(tmp_path: Path) -> None:
    source = build_name_duplicate_estate(tmp_path / "name-dup")
    generated = source / "generated-dir"
    _init_repo(generated, readme="# gen\n")
    (generated / "node_modules" / "pkg").mkdir(parents=True)
    (generated / "node_modules" / "pkg" / "index.js").write_text("1\n", encoding="utf-8")
    parent = source / "nested-parent"
    _init_repo(parent, readme="# Parent\n")
    _init_repo(parent / "vendor" / "nested-child", readme="# Nested\n")
    before = fingerprint(source)
    report = curate(source, output=tmp_path / "win001.json")
    assert fingerprint(source) == before
    assert report["source_mutations"] == 0
    widgets = [item for item in report["inventory"] if item["identity"] == "widget"]
    assert {item["path"] for item in widgets} == {"group-a/widget", "group-b/widget"}
    flagged = next(item for item in widgets if item["duplicate_identity"])
    kept = next(item for item in widgets if not item["duplicate_identity"])
    assert flagged["duplicate_of"] == kept["path"]
    assert "\\" not in flagged["duplicate_of"]
    nested = next(item for item in report["inventory"] if item["nested_repo"])
    assert nested["path"] == "nested-parent/vendor/nested-child"
    assert "\\" not in nested["path"]
    assert any(
        canonicalize_report_path(item).endswith("node_modules")
        for item in report["generated_directories"]
    )
    generated_posix = [
        canonicalize_report_path(item) for item in report["generated_directories"]
    ]
    assert any("/node_modules" in item for item in generated_posix)
    assert kept["path"] in report["recommendation"]["recommended_golden_set"]
    assert flagged["path"] in report["recommendation"]["security_exclusions"]
    assert nested["path"] in report["recommendation"]["security_exclusions"]
    _assert_posix_relative(report)
    payload = json.dumps(report)
    assert r"group-a\\widget" not in payload
    assert "group-a/widget" in payload


def test_ge_win_002_inaccessible_child_and_junction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "estate"
    source.mkdir()
    _init_repo(source / "healthy-git", readme="# Healthy\n")
    locked = source / "locked-reparse"
    locked.mkdir()
    (locked / "README.md").write_text("# locked\n", encoding="utf-8")

    original_lstat = Path.lstat

    def flaky_lstat(self: Path) -> object:
        if self.name == "locked-reparse":
            raise _win1920(self)
        return original_lstat(self)

    monkeypatch.setattr(Path, "lstat", flaky_lstat)
    before = fingerprint(source)
    dest = tmp_path / "win002-lstat.json"
    report = curate(source, output=dest)
    assert fingerprint(source) == before
    assert dest.is_file()
    assert report["source_mutations"] == 0
    names = {item["name"] for item in report["inventory"]}
    assert "healthy-git" in names
    assert "locked-reparse" not in names
    reasons = {item["reason"] for item in report["exclusions"]}
    assert INACCESSIBLE_REASON in reasons
    assert reasons <= EXCLUSION_REASONS
    inaccessible = [item for item in report["exclusions"] if item["reason"] == INACCESSIBLE_REASON]
    assert inaccessible
    assert all(item.get("inspected") is False for item in inaccessible)
    assert "locked-reparse" not in report["recommendation"]["recommended_golden_set"]
    assert report["discovery"]["inaccessible_is_safe"] is False
    assert report["discovery"]["inaccessible_is_golden"] is False
    assert report["discovery"]["skipped_is_scanned"] is False
    assert report["discovery"]["partial"] is True
    assert report["discovery"]["complete"] is False
    assert report["discovery"]["partial_discovery_is_complete_discovery"] is False
    _assert_posix_relative(report)


def test_ge_win_002_iterdir_failure_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "estate"
    source.mkdir()
    _init_repo(source / "healthy-git", readme="# Healthy\n")
    locked = source / "locked-dir"
    locked.mkdir()
    (locked / "README.md").write_text("# locked\n", encoding="utf-8")

    original = Path.iterdir

    def flaky_iterdir(self: Path) -> object:
        if self.name == "locked-dir":
            raise _win1920(self)
        return original(self)

    monkeypatch.setattr(Path, "iterdir", flaky_iterdir)
    dest = tmp_path / "win002-iterdir.json"
    report = curate(source, output=dest)
    assert dest.is_file()
    assert report["source_mutations"] == 0
    names = {item["name"] for item in report["inventory"]}
    assert "healthy-git" in names
    assert INACCESSIBLE_REASON in {item["reason"] for item in report["exclusions"]}
    assert "locked-dir" not in report["recommendation"]["recommended_golden_set"]
    locked = next(item for item in report["inventory"] if item["name"] == "locked-dir")
    assert locked["inspection_complete"] is False
    assert locked["path"] not in report["recommendation"]["recommended_golden_set"]


def test_ge_win_002_secret_scan_metadata_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "estate"
    source.mkdir()
    project = source / "healthy-git"
    _init_repo(project, readme="# Healthy\n")
    probe = project / "notes.txt"
    probe.write_text("ok\n", encoding="utf-8")

    original_stat = Path.stat

    def flaky_stat(self: Path, *args: object, **kwargs: object) -> object:
        if self.name == "notes.txt":
            raise _win1920(self)
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)
    dest = tmp_path / "win002-secret.json"
    report = curate(source, output=dest)
    assert dest.is_file()
    assert report["source_mutations"] == 0
    names = {item["name"] for item in report["inventory"]}
    assert "healthy-git" in names
    assert INACCESSIBLE_REASON in {item["reason"] for item in report["exclusions"]}
    healthy = next(item for item in report["inventory"] if item["name"] == "healthy-git")
    assert healthy["inspection_complete"] is False
    assert healthy["path"] not in report["recommendation"]["recommended_golden_set"]
    payload = json.dumps(report)
    assert WIN1920[1] not in payload


def test_ge_win_002_stale_doc_subtree_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "estate"
    source.mkdir()
    project = source / "stale-docs"
    _init_repo(project, readme="# Old\n")

    original_rglob = Path.rglob

    def flaky_rglob(self: Path, pattern: str) -> object:
        if self.name in {"src", "lib", "app"}:
            raise _win1920(self)
        return original_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", flaky_rglob)
    dest = tmp_path / "win002-stale.json"
    report = curate(source, output=dest)
    assert dest.is_file()
    assert report["source_mutations"] == 0
    names = {item["name"] for item in report["inventory"]}
    assert "stale-docs" in names
    assert INACCESSIBLE_REASON in {item["reason"] for item in report["exclusions"]}
    inaccessible_paths = [
        item["path"]
        for item in report["exclusions"]
        if item["reason"] == INACCESSIBLE_REASON
    ]
    assert inaccessible_paths
    assert all(
        path not in report["recommendation"]["recommended_golden_set"]
        for path in inaccessible_paths
    )
    stale = next(item for item in report["inventory"] if item["name"] == "stale-docs")
    assert stale["inspection_complete"] is False
    assert stale["path"] not in report["recommendation"]["recommended_golden_set"]


def test_ge_win_002_root_inaccessible_is_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "estate"
    source.mkdir()
    original = Path.is_dir

    def flaky_is_dir(self: Path) -> object:
        try:
            if self.resolve() == source.resolve():
                raise _win1920(self)
        except OSError:
            if self == source:
                raise
        return original(self)

    monkeypatch.setattr(Path, "is_dir", flaky_is_dir)
    with pytest.raises(CuratorError) as exc:
        curate(source, output=tmp_path / "should-not-exist.json")
    assert exc.value.code == "SOURCE_ROOT_INACCESSIBLE"
    assert not (tmp_path / "should-not-exist.json").exists()


def test_ge_win_002_permission_error_is_also_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "estate"
    source.mkdir()
    _init_repo(source / "healthy-git", readme="# Healthy\n")
    locked = source / "denied"
    locked.mkdir()

    original = Path.lstat

    def flaky_lstat(self: Path) -> object:
        if self.name == "denied":
            raise PermissionError(13, "Permission denied", str(self))
        return original(self)

    monkeypatch.setattr(Path, "lstat", flaky_lstat)
    report = curate(source, output=tmp_path / "win002-perm.json")
    assert report["source_mutations"] == 0
    assert "healthy-git" in {item["name"] for item in report["inventory"]}
    assert INACCESSIBLE_REASON in {item["reason"] for item in report["exclusions"]}
    assert "denied" not in report["recommendation"]["recommended_golden_set"]


def test_ge_win_002_inaccessible_git_is_not_golden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IV P1: iterdir 1920 on a clean git repo must not recommend golden."""
    source = tmp_path / "estate"
    source.mkdir()
    _init_repo(source / "healthy-git", readme="# Healthy\n")
    _init_repo(source / "locked-git", readme="# Locked\n")

    original = Path.iterdir

    def flaky_iterdir(self: Path) -> object:
        if self.name == "locked-git":
            raise _win1920(self)
        return original(self)

    monkeypatch.setattr(Path, "iterdir", flaky_iterdir)
    dest = tmp_path / "win002-locked-git.json"
    before = fingerprint(source)
    report = curate(source, output=dest)
    assert fingerprint(source) == before
    assert dest.is_file()
    assert report["source_mutations"] == 0
    locked = next(item for item in report["inventory"] if item["name"] == "locked-git")
    healthy = next(item for item in report["inventory"] if item["name"] == "healthy-git")
    assert locked["inspection_complete"] is False
    assert locked["kind"] == "git"
    assert locked["path"] not in report["recommendation"]["recommended_golden_set"]
    assert healthy["path"] in report["recommendation"]["recommended_golden_set"]
    row = next(item for item in report["qualification"] if item["path"] == locked["path"])
    assert row["golden_candidate"] is False
    assert row["excluded"] is True
    assert INACCESSIBLE_REASON in row["blockers"]
    assert report["discovery"]["inaccessible_is_golden"] is False
    assert report["discovery"]["inaccessible_is_safe"] is False
    payload = json.dumps(report)
    assert WIN1920[1] not in payload


def test_ge_win_002_inaccessible_secret_child_blocks_golden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "estate"
    source.mkdir()
    project = source / "secret-locked"
    _init_repo(project, readme="# Secret locked\n")
    env = project / ".env"
    env.write_text("aws_secret_access_key=IV_MUST_NOT_ECHO_THIS_VALUE\n", encoding="utf-8")
    _commit(project, "env", ".env")
    original_stat = Path.stat

    def flaky_stat(self: Path, *args: object, **kwargs: object) -> object:
        if self.name == ".env":
            raise _win1920(self)
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)
    dest = tmp_path / "win002-secret-child.json"
    report = curate(source, output=dest)
    assert dest.is_file()
    assert report["source_mutations"] == 0
    item = next(row for row in report["inventory"] if row["name"] == "secret-locked")
    assert item["path"] not in report["recommendation"]["recommended_golden_set"]
    assert item["secret_findings"] or item["inspection_complete"] is False
    payload = json.dumps(report)
    assert "IV_MUST_NOT_ECHO_THIS_VALUE" not in payload
    assert WIN1920[1] not in payload


def test_ge_win_002_inaccessible_build_script_blocks_golden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "estate"
    source.mkdir()
    project = source / "maybe-malice"
    _init_repo(project, readme="# Maybe\n")
    script = project / "build.sh"
    script.write_text("#!/bin/sh\nrm -rf /tmp/should-not-happen\n", encoding="utf-8")
    _commit(project, "build")
    original = Path.is_file

    def flaky_is_file(self: Path) -> object:
        if self.name == "build.sh":
            raise _win1920(self)
        return original(self)

    monkeypatch.setattr(Path, "is_file", flaky_is_file)
    dest = tmp_path / "win002-malice.json"
    report = curate(source, output=dest)
    assert dest.is_file()
    item = next(row for row in report["inventory"] if row["name"] == "maybe-malice")
    assert item["malicious_build_script"] is False
    assert item["inspection_complete"] is False
    assert item["path"] not in report["recommendation"]["recommended_golden_set"]
    assert not (project / "EXECUTED").exists()


def test_ge_win_002_inaccessible_descendant_blocks_parent_golden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "estate"
    source.mkdir()
    _init_repo(source / "healthy-git", readme="# Healthy\n")
    partial = source / "partial-git"
    _init_repo(partial, readme="# Partial\n")
    locked = partial / "docs" / "locked.bin"
    locked.parent.mkdir()
    locked.write_text("x\n", encoding="utf-8")
    _commit(partial, "docs", "docs/locked.bin")
    dest = tmp_path / "win002-descendant.json"
    before = fingerprint(source)

    original = Path.lstat

    def flaky_lstat(self: Path) -> object:
        if self.name == "locked.bin":
            raise _win1920(self)
        return original(self)

    monkeypatch.setattr(Path, "lstat", flaky_lstat)
    report = curate(source, output=dest)
    monkeypatch.setattr(Path, "lstat", original)
    assert fingerprint(source) == before
    assert dest.is_file()
    healthy = next(item for item in report["inventory"] if item["name"] == "healthy-git")
    blocked = next(item for item in report["inventory"] if item["name"] == "partial-git")
    assert blocked["inspection_complete"] is False
    assert blocked["path"] not in report["recommendation"]["recommended_golden_set"]
    assert healthy["path"] in report["recommendation"]["recommended_golden_set"]
    assert report["discovery"]["inaccessible_is_golden"] is False
    assert any(
        item["path"] == "partial-git/docs/locked.bin"
        for item in report["exclusions"]
        if item["reason"] == INACCESSIBLE_REASON
    )


def test_ge_win_002_disk_estimate_inaccessible_blocks_parent_golden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "estate"
    source.mkdir()
    _init_repo(source / "healthy-git", readme="# Healthy\n")

    def wrapped(root: Path, exclusions: list | None = None) -> dict:
        result = estimate_disk(root, exclusions)
        if exclusions is not None:
            exclusions.append(
                {
                    "path": "healthy-git/docs/estimate-only.bin",
                    "reason": INACCESSIBLE_REASON,
                    "action": "skip",
                    "inspected": False,
                }
            )
        return result

    monkeypatch.setattr(
        "curator.estimate_disk",
        wrapped,
    )
    dest = tmp_path / "win002-disk.json"
    report = curate(source, output=dest)
    assert dest.is_file()
    healthy = next(item for item in report["inventory"] if item["name"] == "healthy-git")
    assert healthy["inspection_complete"] is False
    assert healthy["path"] not in report["recommendation"]["recommended_golden_set"]
    assert report["discovery"]["inaccessible_is_golden"] is False


def test_ge_win_002_root_as_project_inaccessible_descendant_not_golden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "single-repo"
    _init_repo(source, readme="# Root project\n")
    locked = source / "docs" / "locked.bin"
    locked.parent.mkdir()
    locked.write_text("x\n", encoding="utf-8")
    _commit(source, "docs", "docs/locked.bin")
    dest = tmp_path / "win002-root-project.json"
    before = fingerprint(source)
    original = Path.lstat

    def flaky_lstat(self: Path) -> object:
        if self.name == "locked.bin":
            raise _win1920(self)
        return original(self)

    monkeypatch.setattr(Path, "lstat", flaky_lstat)
    report = curate(source, output=dest)
    monkeypatch.setattr(Path, "lstat", original)
    assert fingerprint(source) == before
    assert dest.is_file()
    root_project = next(item for item in report["inventory"] if item["path"] == ".")
    assert root_project["inspection_complete"] is False
    assert "." not in report["recommendation"]["recommended_golden_set"]
    assert report["discovery"]["inaccessible_is_golden"] is False
    assert any(
        item["path"] == "docs/locked.bin"
        for item in report["exclusions"]
        if item["reason"] == INACCESSIBLE_REASON
    )
