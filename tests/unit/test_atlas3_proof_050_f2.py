"""AT3-050-F2 — proof persist is project-bound on the documented task path."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import OPS_RELATIVE, Atlas3Error
from project_atlas.atlas3.proof import evaluate_proof


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    (vault / "projects" / "other-api").mkdir(parents=True)
    return vault


def test_unknown_project_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(Atlas3Error) as exc:
        evaluate_proof(vault, "GHOST", project_id="not-in-vault")
    assert exc.value.code == "UNKNOWN_PROJECT"
    assert not (vault / OPS_RELATIVE / "proof" / "GHOST.json").exists()


def test_foreign_project_does_not_overwrite(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    evaluate_proof(
        vault,
        "SHARED-TASK",
        project_id="harbor-api",
        evidence={"TASK": {"evidence_ref": "harbor-only"}},
    )
    path = vault / OPS_RELATIVE / "proof" / "SHARED-TASK.json"
    before = path.read_bytes()
    with pytest.raises(Atlas3Error) as exc:
        evaluate_proof(
            vault,
            "SHARED-TASK",
            project_id="other-api",
            evidence={"TASK": {"evidence_ref": "other-only"}},
        )
    assert exc.value.code == "PROJECT_MISMATCH"
    assert path.read_bytes() == before


def test_same_project_may_overwrite(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    evaluate_proof(
        vault,
        "HARBOR-TASK",
        project_id="harbor-api",
        evidence={"TASK": {"evidence_ref": "first"}},
    )
    report = evaluate_proof(
        vault,
        "HARBOR-TASK",
        project_id="harbor-api",
        evidence={"TASK": {"evidence_ref": "second"}},
    )
    assert report["project_id"] == "harbor-api"
    assert report["stages"]["TASK"]["evidence_ref"] == "second"
