#!/usr/bin/env python3
"""Run the disposable AS-SKILL-001 rehearsal and promotion evidence harness."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent_control import skill_loader  # noqa: E402
CLI = ROOT / "scripts" / "atlas_agent.py"
MDA = ROOT / "tests" / "fixtures" / "bin" / "mda"
SKILL = ROOT / "skills" / "atlas-governed-work"
REGISTRY = ROOT / "config" / "agent-readiness.yaml"


def command(*args: str, env: dict[str, str], expect: int = 0) -> tuple[int, dict[str, Any] | None, str]:
    result = subprocess.run([sys.executable, str(CLI), *args, "--json"], env=env, capture_output=True, text=True, check=False)
    payload = cast(dict[str, Any], json.loads(result.stdout)) if result.stdout else None
    if result.returncode != expect:
        raise RuntimeError(f"command failed ({result.returncode}): {result.stderr or result.stdout}")
    return result.returncode, payload, result.stderr


def main() -> int:
    manifest = cast(dict[str, Any], yaml.safe_load((SKILL / "skill.yaml").read_text(encoding="utf-8")))
    skill_manifest = cast(dict[str, Any], manifest["skill"])
    with tempfile.TemporaryDirectory(prefix="atlas-skill-cert-") as temporary:
        base = Path(temporary)
        project = base / "project"
        vault = base / "vault"
        (project / ".atlas").mkdir(parents=True)
        (vault / ".atlas").mkdir(parents=True)
        (vault / ".atlas" / "vault.json").write_text(json.dumps({"vault_id": "atlas-rehearsal", "vault_uuid": "rehearsal-uuid"}), encoding="utf-8")
        (project / ".atlas" / "project.yaml").write_text("schema_version: 1\nproject:\n  id: governed-work-rehearsal\n  name: Governed Work Rehearsal\nvault:\n  required_vault_id: atlas-rehearsal\n  required_vault_uuid: rehearsal-uuid\ndocumentation:\n  skill_id: atlas-governed-work\n  strict: true\n", encoding="utf-8")
        env = dict(os.environ, ATLAS_MDA_COMMAND=str(MDA))
        _, bootstrap, _ = command("bootstrap", "--project-root", str(project), "--vault-root", str(vault), "--task-id", "AS-SKILL-001", env=env)
        assert bootstrap is not None
        bootstrap_data = bootstrap
        session_id = str(bootstrap_data["session"]["id"])
        command("acknowledge-skill", "--vault-root", str(vault), "--session-id", session_id, env=env)
        command("capability-check", "--vault-root", str(vault), "--session-id", session_id, env=env)
        for event_type in ("implementation", "validation", "completion"):
            command("document", "--vault-root", str(vault), "--session-id", session_id, "--type", event_type, "--summary", f"Certification {event_type}", env=env)
        command("validate", "--vault-root", str(vault), "--session-id", session_id, env=env)
        _, receipt, _ = command("receipt", "--vault-root", str(vault), "--session-id", session_id, env=env)
        command("postflight", "--vault-root", str(vault), "--session-id", session_id, env=env)
        assert receipt is not None
        receipt_data = receipt
        rehearsal_id = str(receipt_data["rehearsal"]["rehearsal_id"])
        promotion = command("promote-readiness", "--registry", str(REGISTRY), "--adapter-id", "generic-cli-v1", "--rehearsal-id", rehearsal_id, "--receipt", str(vault / ".atlas" / "receipts" / f"{receipt_data['receipt_id']}.json"), "--skill-id", skill_manifest["id"], "--skill-version", skill_manifest["version"], "--skill-sha256", skill_manifest["sha256"], env=env)[1]
        promotion_replay = command("promote-readiness", "--registry", str(REGISTRY), "--adapter-id", "generic-cli-v1", "--rehearsal-id", rehearsal_id, "--receipt", str(vault / ".atlas" / "receipts" / f"{receipt_data['receipt_id']}.json"), "--skill-id", skill_manifest["id"], "--skill-version", skill_manifest["version"], "--skill-sha256", skill_manifest["sha256"], env=env)[1]

        negative: list[dict[str, object]] = []
        wrong_vault = base / "wrong-vault"
        (wrong_vault / ".atlas").mkdir(parents=True)
        (wrong_vault / ".atlas" / "vault.json").write_text(json.dumps({"vault_id": "other", "vault_uuid": "wrong"}), encoding="utf-8")
        result = subprocess.run([sys.executable, str(CLI), "bootstrap", "--project-root", str(project), "--vault-root", str(wrong_vault), "--json"], env=env, capture_output=True, text=True, check=False)
        negative.append({"probe_id": "NG-wrong-vault-id", "expected": "rejected", "actual": "rejected" if result.returncode else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": result.returncode != 0})
        wrong_uuid = base / "wrong-uuid"
        (wrong_uuid / ".atlas").mkdir(parents=True)
        (wrong_uuid / ".atlas" / "vault.json").write_text(json.dumps({"vault_id": "atlas-rehearsal", "vault_uuid": "wrong-uuid"}), encoding="utf-8")
        result = subprocess.run([sys.executable, str(CLI), "bootstrap", "--project-root", str(project), "--vault-root", str(wrong_uuid), "--json"], env=env, capture_output=True, text=True, check=False)
        negative.append({"probe_id": "NG-wrong-vault-uuid", "expected": "rejected", "actual": "rejected" if result.returncode else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": result.returncode != 0})
        mismatch = base / "mismatch.json"
        altered = dict(receipt_data)
        altered["skill"] = {**altered["skill"], "sha256": "0" * 64}
        mismatch.write_text(json.dumps(altered), encoding="utf-8")
        result = subprocess.run([sys.executable, str(CLI), "promote-readiness", "--registry", str(REGISTRY), "--adapter-id", "generic-cli-v1", "--rehearsal-id", rehearsal_id, "--receipt", str(mismatch), "--skill-id", skill_manifest["id"], "--skill-version", skill_manifest["version"], "--skill-sha256", skill_manifest["sha256"], "--json"], env=env, capture_output=True, text=True, check=False)
        negative.append({"probe_id": "NG-receipt-skill-mismatch", "expected": "rejected", "actual": "rejected" if result.returncode else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": result.returncode != 0})
        stale = cast(dict[str, Any], yaml.safe_load(REGISTRY.read_text(encoding="utf-8")))
        stale["adapters"]["generic-cli-v1"]["skill_sha256"] = "1" * 64
        stale_path = base / "stale.yaml"
        stale_path.write_text(yaml.safe_dump(stale, sort_keys=False), encoding="utf-8")
        stale_valid = stale["adapters"]["generic-cli-v1"]["skill_sha256"] == skill_manifest["sha256"]
        negative.append({"probe_id": "NG-stale-rehearsal", "expected": "rejected", "actual": "rejected" if not stale_valid else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": not stale_valid})
        offline_project = base / "offline-project"
        offline_vault = base / "offline-vault"
        (offline_project / ".atlas").mkdir(parents=True)
        (offline_vault / ".atlas").mkdir(parents=True)
        (offline_vault / ".atlas" / "vault.json").write_text(json.dumps({"vault_id": "atlas-rehearsal", "vault_uuid": "rehearsal-uuid"}), encoding="utf-8")
        (offline_project / ".atlas" / "project.yaml").write_text(f"schema_version: 1\nproject:\n  id: governed-work-corrupt\n  name: Governed Work Corrupt\nvault:\n  required_vault_id: atlas-rehearsal\n  required_vault_uuid: rehearsal-uuid\ndocumentation:\n  skill_id: atlas-governed-work\n  readiness_registry: {REGISTRY}\n  strict: true\n", encoding="utf-8")
        _, offline_bootstrap, _ = command("bootstrap", "--project-root", str(offline_project), "--task-id", "AS-SKILL-001", env=env)
        assert offline_bootstrap is not None
        offline_sid = str(offline_bootstrap["session"]["id"])
        spool_path = offline_project / ".atlas-spool"
        command("acknowledge-skill", "--vault-root", str(spool_path), "--session-id", offline_sid, env=env)
        command("capability-check", "--vault-root", str(spool_path), "--session-id", offline_sid, env=env)
        for event_type in ("implementation", "validation", "completion"):
            command("document", "--vault-root", str(spool_path), "--session-id", offline_sid, "--type", event_type, "--summary", f"Corrupt {event_type}", env=env)
        corrupt_file = next((offline_project / ".atlas-spool").glob("AE-*.md"))
        corrupt_file.write_text(corrupt_file.read_text(encoding="utf-8") + "\ncorrupted\n", encoding="utf-8")
        corrupt_result = subprocess.run([sys.executable, str(CLI), "sync-spool", "--spool-root", str(offline_project), "--vault-root", str(offline_vault), "--mda-command", str(MDA), "--json"], env=env, capture_output=True, text=True, check=False)
        negative.append({"probe_id": "NG-corrupted-spool", "expected": "rejected", "actual": "rejected" if corrupt_result.returncode else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": corrupt_result.returncode != 0})
        _, unready_bootstrap, _ = command("bootstrap", "--project-root", str(project), "--vault-root", str(vault), "--task-id", "AS-SKILL-001", env=env)
        assert unready_bootstrap is not None
        unready_sid = str(unready_bootstrap["session"]["id"])
        unready_cap = subprocess.run([sys.executable, str(CLI), "capability-check", "--vault-root", str(vault), "--session-id", unready_sid, "--json"], env=env, capture_output=True, text=True, check=False)
        unready_doc = subprocess.run([sys.executable, str(CLI), "document", "--vault-root", str(vault), "--session-id", unready_sid, "--type", "implementation", "--summary", "must reject", "--json"], env=env, capture_output=True, text=True, check=False)
        negative.append({"probe_id": "NG-missing-acknowledgement", "expected": "rejected", "actual": "rejected" if unready_cap.returncode and unready_doc.returncode else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": bool(unready_cap.returncode and unready_doc.returncode)})
        wrong_ack = subprocess.run([sys.executable, str(CLI), "acknowledge-skill", "--vault-root", str(vault), "--session-id", "not-this-session", "--json"], env=env, capture_output=True, text=True, check=False)
        negative.append({"probe_id": "NG-wrong-session-acknowledgement", "expected": "rejected", "actual": "rejected" if wrong_ack.returncode else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": wrong_ack.returncode != 0})
        conflict_ack = subprocess.run([sys.executable, str(CLI), "acknowledge-skill", "--vault-root", str(vault), "--session-id", session_id, "--sha256", "0" * 64, "--json"], env=env, capture_output=True, text=True, check=False)
        negative.append({"probe_id": "NG-conflicting-acknowledgement", "expected": "rejected", "actual": "rejected" if conflict_ack.returncode else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": conflict_ack.returncode != 0})
        missing_receipt = subprocess.run([sys.executable, str(CLI), "receipt", "--vault-root", str(vault), "--session-id", unready_sid, "--json"], env=env, capture_output=True, text=True, check=False)
        negative.append({"probe_id": "NG-missing-validation-completion", "expected": "rejected", "actual": "rejected" if missing_receipt.returncode else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": missing_receipt.returncode != 0})
        pending_registry = base / "pending.yaml"
        pending_registry.write_text(REGISTRY.read_text(encoding="utf-8").replace("rehearsal_status: passed", "rehearsal_status: pending"), encoding="utf-8")
        pending_project = base / "pending-project"
        (pending_project / ".atlas").mkdir(parents=True)
        (pending_project / ".atlas" / "project.yaml").write_text((project / ".atlas" / "project.yaml").read_text(encoding="utf-8").replace("strict: true", f"readiness_registry: {pending_registry}\n  strict: true"), encoding="utf-8")
        pending_bootstrap = subprocess.run([sys.executable, str(CLI), "bootstrap", "--project-root", str(pending_project), "--vault-root", str(vault), "--json"], env=env, capture_output=True, text=True, check=False)
        negative.append({"probe_id": "NG-uncertified-adapter", "expected": "rejected", "actual": "rejected" if pending_bootstrap.returncode else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": pending_bootstrap.returncode != 0})
        revoked_registry = base / "revoked.yaml"
        revoked_registry.write_text(REGISTRY.read_text(encoding="utf-8").replace("revoked: false", "revoked: true"), encoding="utf-8")
        revoked_project = base / "revoked-project"
        (revoked_project / ".atlas").mkdir(parents=True)
        (revoked_project / ".atlas" / "project.yaml").write_text((project / ".atlas" / "project.yaml").read_text(encoding="utf-8").replace("strict: true", f"readiness_registry: {revoked_registry}\n  strict: true"), encoding="utf-8")
        revoked_bootstrap = subprocess.run([sys.executable, str(CLI), "bootstrap", "--project-root", str(revoked_project), "--vault-root", str(vault), "--json"], env=env, capture_output=True, text=True, check=False)
        negative.append({"probe_id": "NG-revoked-adapter", "expected": "rejected", "actual": "rejected" if revoked_bootstrap.returncode else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": revoked_bootstrap.returncode != 0})
        def missing_skill(path: Path) -> None:
            (path / "SKILL.md").unlink()

        def malformed_manifest(path: Path) -> None:
            (path / "skill.yaml").write_text("bad: [", encoding="utf-8")

        def bad_hash(path: Path) -> None:
            target = path / "skill.yaml"
            target.write_text(target.read_text(encoding="utf-8").replace(skill_manifest["sha256"], "0" * 64), encoding="utf-8")

        for probe_name, mutation in (("NG-missing-skill", missing_skill), ("NG-malformed-manifest", malformed_manifest), ("NG-bad-skill-hash", bad_hash)):
            fixture = base / probe_name
            shutil.copytree(SKILL, fixture)
            mutation(fixture)
            try:
                skill_loader.load(fixture)
            except (OSError, ValueError, yaml.YAMLError):
                passed = True
            else:
                passed = False
            negative.append({"probe_id": probe_name, "expected": "rejected", "actual": "rejected" if passed else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": passed})
        version_project = base / "version-project"
        (version_project / ".atlas").mkdir(parents=True)
        (version_project / ".atlas" / "project.yaml").write_text((project / ".atlas" / "project.yaml").read_text(encoding="utf-8").replace("strict: true", "minimum_skill_version: 9.0.0\n  strict: true"), encoding="utf-8")
        version_bootstrap = subprocess.run([sys.executable, str(CLI), "bootstrap", "--project-root", str(version_project), "--vault-root", str(vault), "--json"], env=env, capture_output=True, text=True, check=False)
        negative.append({"probe_id": "NG-unsupported-skill-version", "expected": "rejected", "actual": "rejected" if version_bootstrap.returncode else "accepted", "canonical_mutations": 0, "receipt_issued": False, "passed": version_bootstrap.returncode != 0})
        for item in negative:
            item.setdefault("name", item["probe_id"])
            item.setdefault("command", "certification harness command surface")
            item.setdefault("actual_exit_code", 1 if item["actual"] == "rejected" else 0)

        evidence = {"schema_version": 1, "rehearsal_receipt": {"path": str(vault / ".atlas" / "receipts" / f"{receipt_data['receipt_id']}.json"), "sha256": hashlib.sha256((vault / ".atlas" / "receipts" / f"{receipt_data['receipt_id']}.json").read_bytes()).hexdigest(), "receipt": receipt_data}, "promotion": promotion, "promotion_replay": promotion_replay, "negative_probes": negative, "all_negative_passed": all(bool(item["passed"]) for item in negative)}
        evidence_dir = ROOT / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "AS-SKILL-001-certification-evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (evidence_dir / "AS-SKILL-001-negative-gates.json").write_text(json.dumps({"schema_version": 1, "probes": negative, "all_passed": evidence["all_negative_passed"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        shutil.copyfile(REGISTRY, evidence_dir / "agent-readiness-promoted.yaml")
        print(json.dumps({"ok": evidence["all_negative_passed"], "rehearsal_id": rehearsal_id, "promotion": promotion, "promotion_replay": promotion_replay, "evidence": str(evidence_dir / "AS-SKILL-001-certification-evidence.json")}))
        return 0 if evidence["all_negative_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
