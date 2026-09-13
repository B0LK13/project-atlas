"""Contain yaml.safe_load constructor KeyError in the control plane.

SEC-015 / fail-closed preflight promised structured ValueError / DENY,
not a raw PyYAML constructor traceback. ``!!bool nope`` raises KeyError
rather than YAMLError. On live main ``b87b4a22`` that leaked from
preflight, readiness, and skill_loader.

Does not authorize readiness. Does not touch Core ``ingestion.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_control import preflight, readiness, skill_loader

MALFORMED = "atlas: !!bool nope\n"


def test_preflight_project_config_constructor_tag_is_invalid(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / ".atlas").mkdir(parents=True)
    (root / ".atlas" / "project.yaml").write_text(MALFORMED, encoding="utf-8")
    with pytest.raises(ValueError, match=r"invalid \.atlas/project\.yaml"):
        preflight.project_config(root)


def test_readiness_check_constructor_tag_denies(tmp_path: Path) -> None:
    registry = tmp_path / "agent-readiness.yaml"
    registry.write_text(MALFORMED, encoding="utf-8")
    report = readiness.check(registry, "generic-cli-v1", "1.0.0", "a" * 64)
    assert report["authorized"] is False
    assert report["status"] == "invalid"


def test_readiness_promote_constructor_tag_is_invalid(tmp_path: Path) -> None:
    registry = tmp_path / "agent-readiness.yaml"
    registry.write_text(MALFORMED, encoding="utf-8")
    with pytest.raises(ValueError, match="invalid readiness registry"):
        readiness.promote(
            registry,
            "generic-cli-v1",
            "atlas-governed-work",
            "1.0.0",
            "a" * 64,
            "reh-1",
            "b" * 64,
            authority_grant={
                "grant_type": "atlas-authority-grant",
                "purpose": "promote-readiness",
                "subject": {
                    "adapter_id": "generic-cli-v1",
                    "skill_id": "atlas-governed-work",
                    "skill_version": "1.0.0",
                    "skill_sha256": "a" * 64,
                },
            },
        )


def test_skill_loader_constructor_tag_is_invalid_manifest(tmp_path: Path) -> None:
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    (skill_root / "skill.yaml").write_text(MALFORMED, encoding="utf-8")
    (skill_root / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid skill manifest"):
        skill_loader.load(skill_root)
