"""Skill schema and hash certification."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parents[1]
DOC = SKILL.parents[1]
if str(DOC) not in sys.path:
    sys.path.insert(0, str(DOC))

from agent_control.skill_loader import load  # noqa: E402


def test_skill_hash_matches_manifest() -> None:
    digest = hashlib.sha256((SKILL / "SKILL.md").read_bytes()).hexdigest()
    listed = (SKILL / "skill.sha256").read_text(encoding="utf-8").split()[0]
    manifest = yaml.safe_load((SKILL / "skill.yaml").read_text(encoding="utf-8"))
    assert digest == listed == manifest["skill"]["sha256"]
    assert manifest["skill"]["id"] == "atlas-golden-estate-curator"
    assert manifest["skill"]["version"] == "1.0.0"
    assert manifest["lifecycle"]["default_mode"] == "DISCOVER_ONLY"
    assert manifest["lifecycle"]["stop_at"] == "OWNER_GATE"


def test_skill_loader_accepts_package() -> None:
    skill = load(SKILL)
    assert skill.skill_id == "atlas-golden-estate-curator"
    assert skill.sha256 == hashlib.sha256((SKILL / "SKILL.md").read_bytes()).hexdigest()
