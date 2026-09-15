#!/usr/bin/env python3
"""Run the AS-CTRL-001 managed-control-plane evidence scenario.

The scenario uses the public ``atlas_agent.py run`` command, two concurrent
managed sessions, and the repository-gate command.  It writes only a compact
evidence summary; disposable project and Vault data are removed with the
temporary directory at process exit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "atlas_agent.py"
MDA = ROOT / "tests" / "fixtures" / "bin" / "mda"
REGISTRY = ROOT / "config" / "agent-readiness.yaml"
CERTIFICATION = ROOT / "AS-SKILL-001-CERTIFICATION-RECEIPT.yaml"
EVIDENCE = ROOT / "evidence" / "AS-CTRL-001-managed-launch.json"


def _run(args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, env=env, capture_output=True, text=True, check=False)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="atlas-ctrl-cert-") as temp:
        temp_root = Path(temp)
        project = temp_root / "project"
        vault = temp_root / "vault"
        (project / ".atlas").mkdir(parents=True)
        (vault / ".atlas").mkdir(parents=True)
        (vault / ".atlas" / "vault.json").write_text(
            json.dumps({"schema_version": 1, "vault_id": "atlas-main", "vault_uuid": "ctrl-cert-uuid"}),
            encoding="utf-8",
        )
        (project / ".atlas" / "project.yaml").write_text(
            "\n".join(
                [
                    "schema_version: 1",
                    "project:",
                    "  id: project-atlas",
                    "  name: Control Plane Certification Fixture",
                    "vault:",
                    "  required_vault_id: atlas-main",
                    "  required_vault_uuid: ctrl-cert-uuid",
                    "documentation:",
                    "  skill_id: atlas-governed-work",
                    f"  readiness_registry: {REGISTRY}",
                    f"  skill_certification: {CERTIFICATION}",
                    "  strict: true",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        child = temp_root / "managed_child.py"
        child.write_text(
            "import json, os, subprocess, sys\n"
            "required = ('ATLAS_PROJECT_ID','ATLAS_VAULT_ID','ATLAS_VAULT_ROOT',"
            "'ATLAS_AGENT_ID','ATLAS_SESSION_ID','ATLAS_SKILL_ID','ATLAS_SKILL_VERSION',"
            "'ATLAS_SKILL_SHA256','ATLAS_ADAPTER_ID','ATLAS_STRICT')\n"
            "assert all(os.environ.get(name) for name in required)\n"
            "out = os.path.join(os.environ['CTRL_EVIDENCE_DIR'], os.environ['ATLAS_SESSION_ID'] + '.json')\n"
            "with open(out, 'w', encoding='utf-8') as handle: json.dump({name: os.environ[name] for name in required}, handle, sort_keys=True)\n"
            "for kind in ('implementation','validation','completion'):\n"
            "  result = subprocess.run([sys.executable, os.environ['ATLAS_CLI'], 'document', '--vault-root', os.environ['ATLAS_VAULT_ROOT'], '--session-id', os.environ['ATLAS_SESSION_ID'], '--type', kind, '--summary', 'control-plane ' + kind, '--json'], check=False)\n"
            "  if result.returncode: raise SystemExit(result.returncode)\n",
            encoding="utf-8",
        )
        env = dict(os.environ, ATLAS_MDA_COMMAND=str(MDA), ATLAS_CLI=str(CLI), CTRL_EVIDENCE_DIR=str(temp_root / "env"))
        (temp_root / "env").mkdir()

        def launch(index: int) -> subprocess.CompletedProcess[str]:
            return _run(
                [
                    sys.executable, str(CLI), "run", "--project-root", str(project),
                    "--vault-root", str(vault), "--agent", "generic",
                    "--agent-id", f"ctrl-cert-agent-{index}", "--task-id",
                    f"AS-CTRL-001-CERT-{index}", "--", sys.executable, str(child),
                ],
                env=env,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            launches = list(pool.map(launch, (1, 2)))
        receipt_paths = sorted((vault / ".atlas" / "receipts").glob("*.json"))
        receipts = [json.loads(path.read_text(encoding="utf-8")) for path in receipt_paths]
        session_ids = [str(item["session"]["session_id"]) for item in receipts]
        session_events = [item["events"].get("session-start", []) for item in receipts]
        gate_missing = _run(
            [sys.executable, str(CLI), "repository-gate", "--project-id", "project-atlas", "--changed-file", "src/example.py", "--json"],
            env=env,
        )
        gate_protected = _run(
            [sys.executable, str(CLI), "repository-gate", "--project-id", "project-atlas", "--changed-file", "projects/project-atlas/events/AE.md", "--json"],
            env=env,
        )
        result: dict[str, Any] = {
            "schema_version": 1,
            "scenario": "AS-CTRL-001 managed launcher and shared Vault",
            "commands": {
                "managed_launch": f"{sys.executable} {CLI} run --project-root <fixture> --vault-root <vault> --agent generic --task-id AS-CTRL-001-CERT-N -- <child>",
                "repository_gate_missing_receipt": f"{sys.executable} {CLI} repository-gate --project-id project-atlas --changed-file src/example.py --json",
                "repository_gate_protected_path": f"{sys.executable} {CLI} repository-gate --project-id project-atlas --changed-file projects/project-atlas/events/AE.md --json",
            },
            "managed_launch": {
                "processes": len(launches),
                "exit_codes": [item.returncode for item in launches],
                "stderr": [item.stderr[-1000:] for item in launches],
                "sessions": session_ids,
                "session_start_event_ids": session_events,
                "receipts": [item.get("receipt_id") for item in receipts],
                "unique_sessions": len(session_ids) == len(set(session_ids)) == 2,
                "unique_events": len({event for events in session_events for event in events}) == 2,
                "pipeline_complete": all(item.get("pipeline", {}).get("captured") == item.get("pipeline", {}).get("routed") == 4 for item in receipts),
                "skill_hashes": sorted({item.get("skill", {}).get("sha256") for item in receipts}),
                "environment_injection": len(list((temp_root / "env").glob("*.json"))) == 2,
            },
            "repository_enforcement": {
                "missing_receipt_exit": gate_missing.returncode,
                "missing_receipt_rejected": gate_missing.returncode != 0,
                "protected_path_exit": gate_protected.returncode,
                "protected_path_rejected": gate_protected.returncode != 0,
            },
            "status": "passed" if all(item.returncode == 0 for item in launches) and gate_missing.returncode != 0 and gate_protected.returncode != 0 else "failed",
        }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
