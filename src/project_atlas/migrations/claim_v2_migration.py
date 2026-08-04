"""Claim Identity v2 migration (AS-CORE-003).

Recompiles historical v1 claim identities from the Git tree of controlled
documentation roots, maps each v1 identity to a stable v2 identity derived
from the durable semantic locator, and emits a durable alias map plus an
audit receipt. Ambiguous mappings are recorded, never silently resolved.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from project_atlas.domain.vocabulary import ClaimType
from project_atlas.schema import validate_record
from project_atlas.source_identity import ProjectIdentityLock

_TOKEN = re.compile(r"[^a-z0-9]+")

_PURPOSE_RE = re.compile(r"^(?:project\s+)?purpose\s*:\s*(.+)$", re.I)
_RUNTIME_RE = re.compile(r"^(?:requires|runtime|dependency)\s*:\s*(.+)$", re.I)
_DEPLOY_RE = re.compile(
    r"^(?:deployment(?:\s+target)?|deploy(?:ed|ment)?\s+target|target)"
    r"\s*:\s*(.+)$",
    re.I,
)
_SETUP_RE = re.compile(r"^(?:setup|install(?:ation)?|requirement)\s*:\s*(.+)$", re.I)
_TEST_RE = re.compile(
    r"^(?:test|validation|acceptance)\s*(?:result|status)?\s*:\s*(.+)$", re.I
)
_ROADMAP_RE = re.compile(r"^(?:roadmap|status)\s*:\s*(.+)$", re.I)
_WORK_PKG_RE = re.compile(r"^(?:work[- ]package)\s*:\s*(.+)$", re.I)
_DECISION_RE = re.compile(r"^(?:decision)\s*:\s*(.+)$", re.I)
_RISK_RE = re.compile(r"^(?:risk|blocker)\s*:\s*(.+)$", re.I)
_OPS_RE = re.compile(r"^(?:run|operate|command|instruction)\s*:\s*(.+)$", re.I)

_LINE_RULES: tuple[tuple[ClaimType, str, re.Pattern[str]], ...] = (
    (ClaimType.PROJECT_PURPOSE, "purpose", _PURPOSE_RE),
    (ClaimType.RUNTIME_DEPENDENCY, "runtime", _RUNTIME_RE),
    (ClaimType.DEPLOYMENT_TARGET, "deployment", _DEPLOY_RE),
    (ClaimType.SETUP_REQUIREMENT, "setup", _SETUP_RE),
    (ClaimType.TEST_RESULT, "validation", _TEST_RE),
    (ClaimType.ROADMAP_STATUS, "roadmap", _ROADMAP_RE),
    (ClaimType.WORK_PACKAGE_STATUS, "work-package", _WORK_PKG_RE),
    (ClaimType.DECISION, "decision", _DECISION_RE),
    (ClaimType.RISK, "risk", _RISK_RE),
    (ClaimType.OPERATIONAL_INSTRUCTION, "operations", _OPS_RE),
)

_SUPERSESSION_RULE = re.compile(
    r"^(?:supersedes|replaces)\s*:\s*([A-Za-z0-9][A-Za-z0-9._-]*)$", re.I
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    result = _TOKEN.sub("-", value.lower()).strip("-")
    return result or "unknown"


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _v1_claim_id(
    project: str, source_id: str, claim_type: str, field: str, value: str
) -> str:
    normalized = " ".join(value.split()).lower()
    key = f"{project}|{source_id}|{claim_type}|{field}|{_digest(normalized)}"
    return f"claim-{_digest(key)[:20]}"


def _v2_claim_id(
    project_identity: str,
    source_lineage_id: str,
    claim_type: str,
    normalized_field: str,
    stable_semantic_locator: str,
) -> str:
    identity_version = "v2"
    key = (
        f"{identity_version}|{project_identity}|{source_lineage_id}|{claim_type}|"
        f"{normalized_field}|{stable_semantic_locator}"
    )
    return f"claim-{_digest(key)[:20]}"


@dataclass(frozen=True)
class _Candidate:
    v1_claim_id: str
    v2_claim_id: str
    project_identity: str
    source_lineage_id: str
    claim_type: str
    field: str
    stable_semantic_locator: str
    source_commit: str
    source_path: str


def _resolve_locator(line: str, current_heading: str | None) -> str | None:
    explicit_match = re.search(r"\{#([^}]+)\}", line)
    if explicit_match:
        return f"id:{explicit_match.group(1).strip()}"
    if current_heading:
        heading_id_match = re.search(r"\{#([^}]+)\}", current_heading)
        if heading_id_match:
            return f"heading:{heading_id_match.group(1).strip()}"
        return f"heading:{_slug(current_heading)}"
    return None


def _extract_candidates(
    project_id: str, path_to_lineage: dict[str, str], commit: str, file_path: str, content: str
) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    source_id = Path(file_path).stem
    source_lineage_id = path_to_lineage.get(file_path) or source_id
    current_heading: str | None = None

    for raw_line in content.splitlines():
        line = raw_line.strip().lstrip("- ").strip()
        if _SUPERSESSION_RULE.match(line):
            continue
        if raw_line.startswith("#"):
            current_heading = raw_line.lstrip("#").strip()
            continue

        for claim_type, field, pattern in _LINE_RULES:
            match = pattern.match(line)
            if not match:
                continue
            claim_value = match.group(1)
            explicit_match = re.search(r"\{#([^}]+)\}", line)
            if explicit_match:
                claim_value = claim_value.replace(explicit_match.group(0), "").strip()

            locator = _resolve_locator(line, current_heading)
            if locator is None:
                continue

            v1_id = _v1_claim_id(project_id, source_id, claim_type.value, field, claim_value)
            v2_id = _v2_claim_id(
                project_id, source_lineage_id, claim_type.value, field, locator
            )
            candidates.append(
                _Candidate(
                    v1_claim_id=v1_id,
                    v2_claim_id=v2_id,
                    project_identity=project_id,
                    source_lineage_id=source_lineage_id,
                    claim_type=claim_type.value,
                    field=field,
                    stable_semantic_locator=locator,
                    source_commit=commit,
                    source_path=file_path,
                )
            )
            break
    return candidates


def _load_path_to_lineage(sources_path: Path) -> dict[str, str]:
    path_to_lineage: dict[str, str] = {}
    if not sources_path.is_file():
        return path_to_lineage
    try:
        data = json.loads(sources_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path_to_lineage
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        return path_to_lineage
    for src in data["sources"]:
        if not isinstance(src, dict):
            continue
        lineage_id = src.get("source_lineage_id")
        if not lineage_id:
            continue
        current_path = src.get("current_path")
        if current_path:
            path_to_lineage[str(current_path)] = str(lineage_id)
        for history in src.get("path_history", []) or []:
            if isinstance(history, dict) and history.get("path"):
                path_to_lineage[str(history["path"])] = str(lineage_id)
    return path_to_lineage


def _scan_historical_sources(vault_root: Path) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Return (commits_scanned, [(commit, path, content), ...]) from Git history."""
    try:
        commits = _run_git(
            ["rev-list", "--all", "--", "sources/"], cwd=vault_root
        ).splitlines()
    except subprocess.CalledProcessError:
        return [], []

    records: list[tuple[str, str, str]] = []
    for commit in commits:
        try:
            files = _run_git(
                ["ls-tree", "-r", "--name-only", commit, "sources/"], cwd=vault_root
            ).splitlines()
        except subprocess.CalledProcessError:
            continue
        for file_path in files:
            if not file_path.endswith(".md"):
                continue
            try:
                content = _run_git(["show", f"{commit}:{file_path}"], cwd=vault_root)
            except subprocess.CalledProcessError:
                continue
            records.append((commit, file_path, content))
    return commits, records


def _candidate_to_record(candidate: _Candidate) -> dict[str, Any]:
    return {
        "v1_claim_id": candidate.v1_claim_id,
        "v2_claim_id": candidate.v2_claim_id,
        "project_identity": candidate.project_identity,
        "source_lineage_id": candidate.source_lineage_id,
        "claim_type": candidate.claim_type,
        "field": candidate.field,
        "stable_semantic_locator": candidate.stable_semantic_locator,
        "source_commit": candidate.source_commit,
        "source_path": candidate.source_path,
    }


def migrate_v2(vault_root: Path, project_id: str) -> dict[str, Any]:
    """Run the v1-to-v2 claim identity migration under a project-scoped guard.

    The migration is idempotent: if a valid alias map already exists, it is
    returned without re-scanning history. Concurrent migrations are rejected
    by an exclusive lock and a compare-and-swap check on the alias map.
    """
    alias_map_path = vault_root / "state" / "claim-alias-map.json"
    lock_path = vault_root / ".atlas" / f"{project_id}-v2-migration.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with ProjectIdentityLock(lock_path, wait_seconds=30.0, stale_seconds=300.0):
        if alias_map_path.is_file():
            existing = json.loads(alias_map_path.read_text(encoding="utf-8"))
            validate_record(existing, "claim-alias")
            return {
                "status": "idempotent",
                "message": "Migration already completed",
                "alias_map_path": str(alias_map_path),
                "migrated_claims": existing["audit"]["output_aliases"],
            }

        path_to_lineage = _load_path_to_lineage(vault_root / "state" / "sources.json")
        commits, records = _scan_historical_sources(vault_root)

        all_candidates: list[_Candidate] = []
        for commit, file_path, content in records:
            all_candidates.extend(
                _extract_candidates(project_id, path_to_lineage, commit, file_path, content)
            )

        aliases: list[dict[str, Any]] = []
        ambiguous: list[dict[str, Any]] = []
        seen: dict[tuple[str, str], _Candidate] = {}
        for candidate in all_candidates:
            key = (candidate.v1_claim_id, candidate.v2_claim_id)
            if key in seen:
                continue
            prior = next(
                (
                    c
                    for c in all_candidates
                    if c.v1_claim_id == candidate.v1_claim_id
                    and c.v2_claim_id != candidate.v2_claim_id
                ),
                None,
            )
            if prior is not None and (prior.v1_claim_id, prior.v2_claim_id) not in seen:
                ambiguous.append(
                    {
                        "v1_claim_id": candidate.v1_claim_id,
                        "reason": "single v1 identity maps to multiple v2 identities",
                        "records": [
                            _candidate_to_record(candidate),
                            _candidate_to_record(prior),
                        ],
                    }
                )
            seen[key] = candidate
            aliases.append(_candidate_to_record(candidate))

        migrated_at = datetime.now(UTC).isoformat()
        alias_payload = {
            "schema_version": 1,
            "project_id": project_id,
            "aliases": aliases,
            "ambiguous": ambiguous,
            "audit": {
                "migrated_at": migrated_at,
                "source_commits_scanned": len(commits),
                "input_claims": len(all_candidates),
                "output_aliases": len(aliases),
            },
        }
        validate_record(alias_payload, "claim-alias")

        alias_map_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = alias_map_path.with_suffix(".tmp")
        try:
            temp_path.write_text(
                json.dumps(alias_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            os.replace(temp_path, alias_map_path)
        except BaseException:
            if temp_path.exists():
                temp_path.unlink()
            raise

        receipt_hash = _digest(json.dumps(alias_payload, sort_keys=True, separators=(",", ":")))
        receipt_name = f"{project_id}-v2-{receipt_hash[:20]}.json"
        receipt_path = vault_root / "receipts" / "migrations" / receipt_name
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_data = {
            "schema_version": 1,
            "receipt_type": "v2-identity-migration",
            "project_id": project_id,
            "migrated_claims": len(aliases),
            "ambiguous_count": len(ambiguous),
            "state_sha256": receipt_hash,
        }
        receipt_path.write_text(
            json.dumps(receipt_data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        return {
            "status": "success",
            "migrated_claims": len(aliases),
            "ambiguous_count": len(ambiguous),
            "receipt": str(receipt_path),
        }

