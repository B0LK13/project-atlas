"""AS-2.0-AGENTOS-001 session envelope tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.agentos import (
    AgentOsError,
    SkillBinding,
    is_protected_path,
    open_session_envelope,
)
from project_atlas.schema import available_schemas, validate_record

ROOT = Path(__file__).resolve().parents[2]


def test_agentos_session_envelope_roundtrip(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = open_session_envelope(
        vault,
        session_id="sess-1",
        task_id="AS-2.0-AGENTOS-001",
        phase="preflight",
        skill=SkillBinding(
            skill_id="atlas-docs",
            skill_sha256="a" * 64,
        ),
    )
    assert report["compat_snapshot_id"] == "atlas-1.0.0-compat"
    assert report["protected_paths_acknowledged"] is True
    validate_record(report, "agentos-session-envelope")
    assert (vault / "generated" / "ops" / "agentos" / "sess-1.json").is_file()


def test_agentos_rejects_bad_skill_hash(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(AgentOsError, match="skill-sha"):
        open_session_envelope(
            vault,
            session_id="sess-2",
            task_id="t",
            skill=SkillBinding(skill_id="x", skill_sha256="nope"),
        )


def test_protected_paths() -> None:
    assert is_protected_path("projects/foo.md")
    assert is_protected_path("routing/state/x.json")
    assert not is_protected_path("generated/ops/health.json")


def test_agentos_docs_and_schema() -> None:
    assert "agentos-session-envelope" in available_schemas()
    assert (ROOT / "docs" / "AS-2.0-AGENTOS-001.md").is_file()
