"""Synchronize approved offline event spool records exactly once."""

from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent_control import receipt_gate, session


def synchronize(spool_root: Path, vault_root: Path, mda_command: str) -> dict[str, Any]:
    spool_root = spool_root.resolve()
    vault_root = vault_root.resolve()
    spool_dir = spool_root / ".atlas-spool" if (spool_root / ".atlas-spool").is_dir() else spool_root
    state_dir = spool_dir / ".atlas" / "sessions" if (spool_dir / ".atlas" / "sessions").is_dir() else spool_root / ".atlas" / "sessions"
    state_files = list(state_dir.glob("*.json"))
    events = sorted(spool_dir.glob("AE-*.md"))
    if not state_files:
        raise ValueError("offline session state is missing")
    state = json.loads(state_files[0].read_text(encoding="utf-8"))
    if state.get("skill_acknowledgement", {}).get("sha256") != state.get("skill", {}).get("sha256"):
        raise ValueError("spool skill acknowledgement mismatch")
    if state.get("preflight", {}).get("readiness", {}).get("authorized") is False:
        raise ValueError("spool adapter readiness is not authorized")
    if not events:
        existing_path = vault_root / ".atlas" / "sessions" / state_files[0].name
        if existing_path.is_file():
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
            return {"ok": True, "spool": {"discovered": 0, "accepted": 0, "synchronized": 0, "rejected": 0, "remaining": 0}, "pipeline": existing.get("pipeline", {}), "session_id": existing.get("session", {}).get("session_id"), "receipt_id": existing.get("receipt_id"), "copied": 0, "idempotent": True}
    expected_hashes = state.get("spool_hashes", {})
    corrupted = [path.name for path in events if expected_hashes.get(path.stem) and expected_hashes[path.stem] != hashlib.sha256(path.read_bytes()).hexdigest()]
    if corrupted:
        raise ValueError("spool record hash mismatch: " + ", ".join(corrupted))
    vault_root.mkdir(parents=True, exist_ok=True)
    (vault_root / ".atlas").mkdir(parents=True, exist_ok=True)
    copied = 0
    normalized = 0
    routed = 0
    for source in events:
        destination = vault_root / "sources" / "agent-events" / "spool" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)
            copied += 1
        normalize = Path(__file__).resolve().parents[1] / "scripts" / "normalize_event.py"
        route = Path(__file__).resolve().parents[1] / "scripts" / "route_event.py"
        result = subprocess.run([sys.executable, str(normalize), "--event", str(destination), "--root", str(vault_root), "--mda-command", mda_command, "--skill-dir", str(Path(__file__).resolve().parents[1]), "--skill", "atlas-governed-work", "--json"], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "spool normalization failed")[-1000:])
        normalized_payload = json.loads(result.stdout)
        result = subprocess.run([sys.executable, str(route), "--normalized-event", str(normalized_payload["normalized_event"]), "--vault", str(vault_root), "--json"], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "spool routing failed")[-1000:])
        normalized += 1
        routed += 1
        source.unlink()
    synced_state = json.loads(json.dumps(state))
    synced_state["vault"]["root"] = str(vault_root)
    synced_state["pipeline"]["normalized"] = int(synced_state["pipeline"].get("normalized", 0)) + normalized
    synced_state["pipeline"]["verified"] = int(synced_state["pipeline"].get("verified", 0)) + normalized
    synced_state["pipeline"]["routed"] = int(synced_state["pipeline"].get("routed", 0)) + routed
    synced_state["pipeline"]["pending_spool"] = 0
    synced_state["status"] = "active"
    session.save(vault_root, synced_state)
    receipt = receipt_gate.issue(vault_root, synced_state)
    return {"ok": True, "spool": {"discovered": len(events), "accepted": len(events), "synchronized": routed, "rejected": 0, "remaining": len(list(spool_dir.glob("AE-*.md")))}, "pipeline": synced_state["pipeline"], "session_id": synced_state["session"]["session_id"], "receipt_id": receipt["receipt_id"], "copied": copied}
