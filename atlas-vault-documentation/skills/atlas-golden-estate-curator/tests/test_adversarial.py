"""Adversarial fail-closed tests for the golden estate curator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from curator import CuratorError, curate, main, reject_mutation  # noqa: E402
from estate import fingerprint  # noqa: E402


@pytest.mark.parametrize(
    "action",
    ["DELETE", "MOVE", "RENAME", "GIT_CLEAN", "GIT_RESET", "AUTO_COMMIT", "AUTO_PUSH"],
)
def test_mutation_actions_fail_closed(action: str) -> None:
    with pytest.raises(CuratorError) as exc:
        reject_mutation(action)
    assert exc.value.code == "MUTATION_FORBIDDEN"


@pytest.mark.parametrize("phase", ["COPY", "GOLDENIZE", "BASELINE_FREEZE", "FREEZE_ESTATE"])
def test_owner_gated_phases_fail_closed(tmp_path: Path, fixture_estate: Path, phase: str) -> None:
    source = fixture_estate
    with pytest.raises(CuratorError) as exc:
        curate(source, phase=phase, owner_authorize_copy=True)
    assert exc.value.code == "OWNER_GATE_REQUIRED"
    assert not (source / "malicious-build" / "EXECUTED").exists()


def test_cli_delete_and_git_clean_fail(tmp_path: Path, fixture_estate: Path) -> None:
    source = fixture_estate
    before = fingerprint(source)
    assert main(["--source-root", str(source), "--action", "DELETE"]) == 1
    assert main(["--source-root", str(source), "--action", "GIT_CLEAN"]) == 1
    assert main(["--source-root", str(source), "--phase", "COPY"]) == 1
    assert fingerprint(source) == before
    assert (source / "dirty-worktree" / "scratch.txt").is_file()


def test_path_traversal_and_unc_fail() -> None:
    with pytest.raises(CuratorError) as trav:
        curate("../etc")
    assert trav.value.code == "PATH_TRAVERSAL"
    with pytest.raises(CuratorError) as unc:
        curate(r"\\server\share")
    assert unc.value.code == "UNC_PATH_REJECTED"


def test_symlink_escape_and_secret_and_malice(tmp_path: Path, fixture_estate: Path) -> None:
    source = fixture_estate
    report = curate(source, output=tmp_path / "out.json")
    reasons = {item["reason"] for item in report["exclusions"]}
    assert "SYMLINK_OR_JUNCTION_ESCAPE" in reasons
    secret = next(item for item in report["inventory"] if item["name"] == "fake-secret")
    assert secret["secret_findings"]
    assert "NOT_A_REAL_SECRET_VALUE" not in json_blob(report)
    malice = next(item for item in report["inventory"] if item["name"] == "malicious-build")
    assert malice["malicious_build_script"] is True
    assert malice["executed_build"] is False
    assert not (source / "malicious-build" / "EXECUTED").exists()
    nested = [item for item in report["inventory"] if item["nested_repo"]]
    assert nested
    dirty = next(item for item in report["inventory"] if item["name"] == "dirty-worktree")
    assert dirty["dirty_worktree"] is True
    assert (source / "dirty-worktree" / "scratch.txt").read_text(encoding="utf-8") == "uncommitted\n"


def test_long_windows_path_is_classified(tmp_path: Path) -> None:
    source = tmp_path / "estate"
    source.mkdir()
    deep = source / ("W" * 250)
    # Creating an over-long directory may fail on some filesystems; classify either way.
    try:
        deep.mkdir()
        (deep / "README.md").write_text("# long\n", encoding="utf-8")
    except OSError:
        pytest.skip("filesystem rejected long path creation")
    report = curate(source, output=tmp_path / "long.json")
    assert any(item["reason"] == "LONG_PATH" for item in report["exclusions"]) or any(
        item["name"].startswith("W") for item in report["inventory"]
    )


def json_blob(report: dict) -> str:
    import json

    return json.dumps(report)
