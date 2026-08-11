"""Fail-closed managed-agent preflight."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from agent_control import adapter_registry, agent_identity, readiness, skill_loader, vault_identity


def project_config(project_root: Path) -> dict[str, Any]:
    path = project_root / ".atlas" / "project.yaml"
    if not path.is_file():
        raise ValueError(f"project Atlas configuration is missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("project"), dict):
        raise ValueError("invalid .atlas/project.yaml")
    return data


def run(*, project_root: Path, vault_root: Path | None, agent_type: str, agent_value: str | None, skill_root: Path) -> dict[str, Any]:
    config = project_config(project_root)
    project = config["project"]
    documentation = config.get("documentation", {}) if isinstance(config.get("documentation", {}), dict) else {}
    vault_cfg = config.get("vault", {}) if isinstance(config.get("vault", {}), dict) else {}
    skill = skill_loader.load(skill_root)
    configured_skill = str(documentation.get("skill_id", ""))
    if configured_skill and configured_skill != skill.skill_id:
        raise ValueError(f"configured skill does not match resolved skill: {configured_skill} != {skill.skill_id}")
    certification_value = documentation.get("skill_certification")
    if certification_value:
        certification_path = Path(str(certification_value))
        if not certification_path.is_absolute():
            certification_path = project_root / certification_path
        if not certification_path.is_file():
            raise ValueError("certified skill receipt is missing")
        certification = yaml.safe_load(certification_path.read_text(encoding="utf-8"))
        certified_skill = certification.get("skill", {}) if isinstance(certification, dict) else {}
        if not isinstance(certification, dict) or certification.get("status") != "certified" or certified_skill.get("id") != skill.skill_id or certified_skill.get("version") != skill.version or certified_skill.get("sha256") != skill.sha256:
            raise ValueError("certified skill dependency does not match resolved skill")
    minimum_skill = str(documentation.get("minimum_skill_version", "1.0.0"))
    if not skill.version_at_least(minimum_skill):
        raise ValueError(f"outdated Atlas skill: {skill.version} < {minimum_skill}")
    required_id = str(vault_cfg.get("required_vault_id", "")) or None
    required_uuid = str(vault_cfg.get("required_vault_uuid", "")) or None
    spool_mode = vault_root is None and not __import__("os").environ.get("ATLAS_VAULT_ROOT")
    if spool_mode:
        spool_root = project_root / ".atlas-spool"
        spool_root.mkdir(parents=True, exist_ok=True)
        identity_data = {"vault_id": required_id or "unknown", "vault_uuid": required_uuid or "unknown", "root": str(spool_root.resolve())}
    else:
        identity = vault_identity.resolve(cli_root=vault_root, required_id=required_id, required_uuid=required_uuid)
        identity_data = {"vault_id": identity.vault_id, "vault_uuid": identity.vault_uuid, "root": str(identity.root)}
    agent = agent_identity.agent_id(agent_value, agent_type)
    adapter = adapter_registry.get(agent_type)
    readiness_path_value = documentation.get("readiness_registry")
    readiness_path = Path(str(readiness_path_value)).expanduser() if readiness_path_value else None
    readiness_report = readiness.check(readiness_path, str(adapter["adapter_id"]), skill.version, skill.sha256)
    # SEC-015: missing / unauthorized readiness always fails closed (no legacy allow).
    if not readiness_report["authorized"]:
        raise ValueError(f"adapter is not ready for governed work: {readiness_report['reason']}")
    spool = project_root / ".atlas-spool"
    spool.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "project_id": str(project["id"]), "project_root": str(project_root.resolve()), "vault": identity_data, "spool": {"root": str(spool), "available": spool.is_dir(), "mode": spool_mode}, "skill": {"id": skill.skill_id, "version": skill.version, "sha256": skill.sha256, "path": str(skill.path)}, "skill_certification": str(documentation.get("skill_certification", "")) or None, "agent": {"agent_id": agent, **adapter}, "readiness": readiness_report, "strict": bool(documentation.get("strict", True)), "receipt_required": bool(documentation.get("require_receipt", True))}
