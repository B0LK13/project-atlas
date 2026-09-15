"""Canonical skill loading and hash verification."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Skill:
    skill_id: str
    version: str
    path: Path
    sha256: str

    def version_at_least(self, minimum: str) -> bool:
        def parts(value: str) -> tuple[int, ...]:
            return tuple(int(item) for item in value.split(".") if item.isdigit())
        return parts(self.version) >= parts(minimum)


def load(skill_root: Path) -> Skill:
    manifest_path = skill_root / "skill.yaml"
    if not manifest_path.is_file():
        manifest_path = skill_root / "skill-manifest.yaml"
    skill_path = skill_root / "SKILL.md"
    if not manifest_path.is_file() or not skill_path.is_file():
        raise ValueError("canonical Atlas skill or manifest is missing")
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("skill"), dict):
        raise ValueError("invalid skill manifest")
    values = data["skill"]
    actual = hashlib.sha256(skill_path.read_bytes()).hexdigest()
    expected = str(values.get("sha256", ""))
    if expected == "PENDING_GENERATION" or actual != expected:
        raise ValueError(f"canonical skill hash mismatch: expected {expected}, actual {actual}")
    return Skill(str(values.get("id", "")), str(values.get("version", "")), skill_path.resolve(), actual)
