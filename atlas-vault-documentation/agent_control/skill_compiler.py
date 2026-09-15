"""Deterministic generated instruction adapters."""

from __future__ import annotations

from pathlib import Path

from agent_control.skill_loader import Skill


def render(skill: Skill, adapter_id: str, project_id: str = "<project-id>", vault_id: str = "<vault-id>") -> str:
    return f"""GENERATED FILE — DO NOT EDIT DIRECTLY
Canonical source: {skill.path}
Skill ID: {skill.skill_id}
Skill version: {skill.version}
Skill SHA-256: {skill.sha256}
Adapter: {adapter_id}
Project: {project_id}
Vault: {vault_id}

This repository uses the Atlas governed-work protocol.

Before performing project work:
1. Run `atlas-agent bootstrap --project-root <project-root> --json`.
2. Read the resolved operational skill returned by bootstrap.
3. Run the capability preflight requested by bootstrap.
4. Stop when bootstrap or preflight fails; do not modify project files.
5. Use `atlas-agent document` for documentation events.
6. Do not report completion without a validated ATLAS-DOC-RECEIPT.
"""


def generate(skill: Skill, output_root: Path, *, project_id: str = "<project-id>", vault_id: str = "<vault-id>") -> list[Path]:
    paths: list[Path] = []
    for name, adapter_id in (("generic", "generic-cli-v1"), ("cli-agents", "generic-cli-v1"), ("ide-agents", "ide-agent-v1"), ("repository-agents", "repository-agent-v1"), ("remote-agents", "remote-agent-v1")):
        target = output_root / name / "ATLAS-INSTRUCTIONS.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(skill, adapter_id, project_id, vault_id), encoding="utf-8")
        paths.append(target)
    return paths


def verify(skill: Skill, output_root: Path, *, project_id: str = "<project-id>", vault_id: str = "<vault-id>") -> list[str]:
    errors: list[str] = []
    expected = {path: render(skill, adapter, project_id, vault_id) for path, adapter in ((output_root / name / "ATLAS-INSTRUCTIONS.md", adapter_id) for name, adapter_id in (("generic", "generic-cli-v1"), ("cli-agents", "generic-cli-v1"), ("ide-agents", "ide-agent-v1"), ("repository-agents", "repository-agent-v1"), ("remote-agents", "remote-agent-v1")))}
    for path, content in expected.items():
        if not path.is_file():
            errors.append(f"missing adapter: {path}")
        elif path.read_text(encoding="utf-8") != content:
            errors.append(f"adapter drift: {path}")
    return errors
