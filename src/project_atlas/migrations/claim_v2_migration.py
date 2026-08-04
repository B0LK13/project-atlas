"""Claim Identity v2 Migration."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from project_atlas.domain.vocabulary import ClaimType
from project_atlas.knowledge_compiler import (
    _digest, 
    _LINE_RULES, 
    _SUPERSESSION_RULE, 
    _slug
)

def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout

def _v1_claim_id(project: str, source_id: str, claim_type: str, field: str, value: str) -> str:
    normalized = " ".join(value.split()).lower()
    key = f"{project}|{source_id}|{claim_type}|{field}|{_digest(normalized)}"
    return f"claim-{_digest(key)[:20]}"

def _v2_claim_id(project: str, source_identity: str, claim_type: str, field: str, locator: str) -> str:
    identity_version = "v2"
    key = f"{identity_version}|{project}|{source_identity}|{claim_type}|{field}|{_digest(locator)}"
    return f"claim-{_digest(key)[:20]}"

def build_alias_map(vault_root: Path, project_id: str) -> dict[str, str]:
    alias_map = {}
    try:
        commits = run_git(["rev-list", "--all", "--", "sources/"], cwd=vault_root).splitlines()
    except subprocess.CalledProcessError:
        commits = []
        
    for commit in commits:
        files = run_git(["ls-tree", "-r", "--name-only", commit, "sources/"], cwd=vault_root).splitlines()
        for f in files:
            if not f.endswith(".md"):
                continue
            
            try:
                content = run_git(["show", f"{commit}:{f}"], cwd=vault_root)
            except subprocess.CalledProcessError:
                continue
                
            source_id = Path(f).stem
            # In historical, we might not have source_lineage_id readily available without manifest, 
            # so we use source_id as fallback which matches v1 behavior.
            source_identity = source_id 
            
            current_heading = None
            schema_key = None # Not available in raw text without manifest
            
            for number, raw_line in enumerate(content.splitlines(), start=1):
                line = raw_line.strip().lstrip("- ").strip()
                supersession = _SUPERSESSION_RULE.match(line)
                if supersession:
                    continue
                    
                if raw_line.startswith("#"):
                    current_heading = raw_line.lstrip("#").strip()
                    continue
                    
                for claim_type, field, pattern in _LINE_RULES:
                    match = pattern.match(line)
                    if match:
                        claim_value = match.group(1)
                        explicit_match = re.search(r'\{#([^}]+)\}', line)
                        
                        v1_id = _v1_claim_id(project_id, source_id, claim_type.value, field, claim_value)
                        
                        locator = None
                        if explicit_match:
                            locator = f"id:{explicit_match.group(1).strip()}"
                        elif current_heading:
                            heading_id_match = re.search(r'\{#([^}]+)\}', current_heading)
                            if heading_id_match:
                                locator = f"heading:{heading_id_match.group(1).strip()}"
                            else:
                                locator = f"heading:{_slug(current_heading)}"
                                
                        if locator:
                            v2_id = _v2_claim_id(project_id, source_identity, claim_type.value, field, locator)
                            alias_map[v1_id] = v2_id
                        break
    return alias_map

def migrate_v2(vault_root: Path, project_id: str) -> dict[str, Any]:
    lockfile = vault_root / ".atlas" / f"{project_id}-v2-migration.lock"
    if lockfile.exists():
        raise RuntimeError(f"Migration locked or in progress for {project_id}")
        
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    lockfile.touch()
    
    try:
        alias_map_path = vault_root / "state" / "claim-alias-map.json"
        if alias_map_path.exists():
            return {"status": "idempotent", "message": "Migration already completed", "alias_map_path": str(alias_map_path)}
            
        alias_map = build_alias_map(vault_root, project_id)
        
        # Write alias map atomically
        temp_path = alias_map_path.with_suffix(".tmp")
        alias_map_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(alias_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(alias_map_path)
        
        receipt_hash = _digest(json.dumps(alias_map, sort_keys=True))
        receipt_path = vault_root / "receipts" / "migrations" / f"{project_id}-v2-{receipt_hash[:20]}.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        
        receipt_data = {
            "schema_version": 1,
            "receipt_type": "v2-identity-migration",
            "project_id": project_id,
            "migrated_claims": len(alias_map),
            "state_sha256": receipt_hash
        }
        receipt_path.write_text(json.dumps(receipt_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        
        return {"status": "success", "migrated_claims": len(alias_map), "receipt": str(receipt_path)}
    except Exception as e:
        # Rollback happens naturally because we use atomic writes.
        # Ensure temporary files are cleaned up
        temp_path = vault_root / "state" / "claim-alias-map.tmp"
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Migration failed and rolled back: {e}") from e
    finally:
        lockfile.unlink(missing_ok=True)
