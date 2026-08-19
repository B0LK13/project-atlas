"""Governed discovery-to-route orchestration for AS-WP-004."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from internal import (
    atlas_router,
    documentation_conflicts,
    documentation_coverage,
    document_inventory,
    ingestion_planner,
    ingestion_projection,
    ingestion_state,
    project_discovery,
)
from internal.mda_output_contract import (
    RESTRUCTURED_SUFFIX,
    is_mda_output_artifact,
)


class IngestionError(RuntimeError):
    """A strict ingestion operation failed."""


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_immutable_json(path: Path, value: dict[str, Any]) -> None:
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.is_file():
        if path.read_text(encoding="utf-8") != content:
            raise IngestionError(f"immutable receipt collision: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _snapshot_vault(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }


def _restore_vault(root: Path, snapshot: dict[Path, bytes]) -> None:
    for path in root.rglob("*"):
        if path.is_file() and path.relative_to(root) not in snapshot:
            path.unlink()
    for relative, content in snapshot.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def _run(argv: list[str], *, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(argv, capture_output=True, text=True, env=env, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "command failed").strip()[-1000:]
        raise IngestionError(f"{Path(argv[1]).name} failed ({result.returncode}): {detail}")


def _receipt_id(project_id: str, inventory_sha256: str) -> str:
    return f"AI-{inventory_sha256[:16]}-{project_id}"


def _project_event_id(document_id: str, sha256: str) -> str:
    digest = hashlib.sha256(f"{document_id}|{sha256}".encode("utf-8")).hexdigest()[:32]
    return f"AI-{digest}"


def ingest_project(
    project: project_discovery.ProjectRecord,
    *,
    vault_root: Path,
    config: dict[str, Any] | None = None,
    incremental: bool = True,
    dry_run: bool = False,
    strict: bool = True,
    mda_command: str = "mda",
) -> dict[str, Any]:
    """Inventory and optionally process one project through the certified path."""
    config = config or {}
    effective_config = dict(config)
    if project.authority and "authority" not in effective_config:
        effective_config["authority"] = project.authority
    inventory = document_inventory.inventory_project(Path(project.root), project_id=project.project_id, config=effective_config)
    state_path = vault_root / "ingestion" / "state" / f"{project.project_id}.json"
    previous = ingestion_state.load_state(state_path, project.project_id)
    diff = ingestion_state.diff_inventory(inventory, previous) if incremental else {
        "new": list(inventory["documents"]), "changed": [], "unchanged": [], "deleted": [], "renamed": []
    }
    plan = ingestion_planner.build_plan(inventory, diff, incremental=incremental)
    counts = {
        "files_discovered": len(inventory["documents"]),
        "files_eligible": sum(1 for item in inventory["documents"] if item["processing"]["eligibility"] == "eligible"),
        "files_excluded": sum(1 for item in inventory["documents"] if item["processing"]["eligibility"] != "eligible"),
        "files_sensitive": sum(1 for item in inventory["documents"] if item["security"]["sensitivity"] == "sensitive"),
        "files_unsupported": sum(1 for item in inventory["documents"] if item["processing"]["state"] == "unsupported"),
        "files_new": len(diff["new"]), "files_changed": len(diff["changed"]),
        "files_unchanged": len(diff["unchanged"]), "files_deleted": len(diff["deleted"]), "files_renamed": len(diff.get("renamed", [])),
    }
    if dry_run:
        return {"ok": True, "status": "dry-run", "project": project.as_dict(), "inventory": inventory, "plan": plan, "counts": counts}

    if not diff["new"] and not diff["changed"] and not diff["deleted"] and not diff.get("renamed") and previous.get("last_receipt"):
        receipt_dir = vault_root / "ingestion" / "receipts"
        for receipt_path in sorted(receipt_dir.glob(f"{project.project_id}-*.json")):
            candidate = json.loads(receipt_path.read_text(encoding="utf-8"))
            if candidate.get("receipt_id") == previous["last_receipt"]:
                result_receipt = dict(candidate)
                result_receipt["transaction"] = dict(candidate.get("transaction", {}), no_op=True)
                return {
                    "ok": True, "status": "no-op", "project_id": project.project_id,
                    "inventory": inventory, "plan": plan, "counts": counts,
                    "processing": {"captured": 0, "normalized": 0, "verified": 0, "routed": 0, "quarantined": 0, "failed": 0},
                    "coverage": documentation_coverage.assess(inventory),
                    "conflicts": documentation_conflicts.detect(inventory, project.root),
                    "receipt": result_receipt,
                }

    vault_snapshot = _snapshot_vault(vault_root) if vault_root.exists() else {}
    base = vault_root / "ingestion"
    _write_json(base / "inventory" / f"{project.project_id}.json", inventory)
    _write_json(base / "plans" / f"{project.project_id}-{plan['plan_sha256'][:12]}.json", plan)
    state = ingestion_state.apply_inventory(previous, inventory, diff)
    processed = {"captured": 0, "normalized": 0, "verified": 0, "routed": 0, "quarantined": 0, "failed": 0}
    timings = {"capture": 0.0, "normalize_verify": 0.0, "route": 0.0}
    scripts = Path(__file__).resolve().parent.parent / "scripts"
    for operation in plan["operations"]:
        if operation["action"] != "ingest":
            continue
        item = next(item for item in inventory["documents"] if item["document_id"] == operation["document_id"])
        event_id = _project_event_id(str(item["document_id"]), str(item["sha256"]))
        try:
            started = time.perf_counter()
            _run([
                sys.executable, str(scripts / "capture_event.py"), "--vault", str(vault_root),
                "--project-id", f"PRJ-{project.project_id.upper().replace('-', '-')}",
                "--project-slug", project.project_id, "--event-kind", "documentation",
                "--summary", f"Ingest documentation: {item['relative_path']}", "--agent", "atlas-ingestion",
                "--event-id", event_id, "--repository", project.project_id,
                "--changed-file", str(item["relative_path"]), "--evidence", f"sha256:{item['sha256']}",
                "--outcome", f"classification={item['classification']['type']}; authority={item['authority']['level']}",
            ])
            timings["capture"] += time.perf_counter() - started
            processed["captured"] += 1
            raw_candidates = sorted(
                path for path in vault_root.rglob(f"{event_id}.md")
                if path.is_file() and not is_mda_output_artifact(path.name)
            )
            if len(raw_candidates) != 1:
                raise IngestionError(f"capture produced {len(raw_candidates)} raw artifacts for {event_id}")
            raw = raw_candidates[0]
            normalized = raw.with_name(f"{event_id}{RESTRUCTURED_SUFFIX}")
            started = time.perf_counter()
            _run([
                sys.executable, str(scripts / "normalize_event.py"), "--event", str(raw),
                "--root", str(vault_root), "--mda-command", mda_command,
                "--skill-dir", str(scripts.parent),
            ])
            timings["normalize_verify"] += time.perf_counter() - started
            processed["normalized"] += 1
            processed["verified"] += 1
            started = time.perf_counter()
            _run([
                sys.executable, str(scripts / "route_event.py"), "--normalized-event", str(normalized),
                "--vault", str(vault_root), "--json",
            ])
            timings["route"] += time.perf_counter() - started
            processed["routed"] += 1
            state["documents"][str(item["document_id"])] ["state"] = "routed"
            state["documents"][str(item["document_id"])] ["route_event_ids"] = [event_id]
        except (OSError, IngestionError) as exc:
            processed["failed"] += 1
            state["documents"][str(item["document_id"])] ["state"] = "failed"
            state["documents"][str(item["document_id"])] ["failure"] = str(exc)
            if strict:
                _restore_vault(vault_root, vault_snapshot)
                failure_path = vault_root / "ingestion" / "failures" / f"{project.project_id}-{item['sha256'][:16]}.json"
                _write_json(failure_path, {"schema_version": 1, "project_id": project.project_id, "document_id": item["document_id"], "category": "strict-transaction-failed", "message": str(exc)[:1000]})
                raise
            processed["quarantined"] += 1

    coverage = documentation_coverage.assess(inventory)
    conflicts = documentation_conflicts.detect(inventory, project.root)
    map_content = ingestion_projection.render_map(inventory, coverage, conflicts)
    map_target = vault_root / "projects" / project.project_id / "documentation-map.md"
    map_existed = map_target.is_file()
    changed_map, no_op_map = atlas_router.update_documentation_map(
        vault_root=vault_root, project_id=project.project_id, content=map_content,
        settings=atlas_router.RoutingSettings(),
    )
    ingestion_state.save_state(state_path, state)
    _write_json(base / "coverage" / f"{project.project_id}.json", coverage)
    _write_json(base / "conflicts" / f"{project.project_id}.json", {"project_id": project.project_id, "conflicts": conflicts})
    is_no_op = not diff["new"] and not diff["changed"] and not diff["deleted"] and not diff.get("renamed") and no_op_map
    if is_no_op and previous.get("last_receipt"):
        for receipt_path in sorted((base / "receipts").glob(f"{project.project_id}-*.json")):
            candidate = json.loads(receipt_path.read_text(encoding="utf-8"))
            if candidate.get("receipt_id") == previous["last_receipt"]:
                ingestion_state.save_state(state_path, state)
                result_receipt = dict(candidate)
                result_receipt["transaction"] = dict(candidate.get("transaction", {}), no_op=True)
                return {"ok": True, "status": "no-op", "project_id": project.project_id, "inventory": inventory, "plan": plan, "counts": counts, "processing": processed, "coverage": coverage, "conflicts": conflicts, "receipt": result_receipt}
    receipt_id = _receipt_id(project.project_id, inventory["inventory_sha256"])
    receipt = {
        "schema_version": 1, "receipt_type": "atlas-project-ingestion", "receipt_id": receipt_id,
        "project": {"project_id": project.project_id, "project_name": project.name, "project_root": project.root, "identity_source": project.identity_source},
        "inventory": {**counts, "inventory_sha256": inventory["inventory_sha256"]},
        "processing": processed,
        "documentation": {"classifications": {}, "coverage_complete": coverage["counts"]["complete"], "coverage_partial": coverage["counts"]["partial"], "coverage_missing": coverage["counts"]["missing"], "conflicts": len(conflicts), "stale_records": len(diff["deleted"])},
        "graphify": {"files_discovered": sum(1 for item in inventory["documents"] if item["classification"]["type"] == "graphify-output"), "files_inventoried": sum(1 for item in inventory["documents"] if item["classification"]["type"] == "graphify-output"), "semantic_ingestion": "deferred", "authority": "derived"},
        "transaction": {"transaction_id": f"AITX-{inventory['inventory_sha256'][:16]}", "plan_sha256": plan["plan_sha256"], "previous_receipt": previous.get("last_receipt"), "no_op": is_no_op},
        "validation": {"status": "passed", "errors": 0, "warnings": len(conflicts)},
        "atlas_updates": {"created": [f"projects/{project.project_id}/documentation-map.md"] if changed_map and not map_existed else [], "modified": [f"projects/{project.project_id}/documentation-map.md"] if changed_map and map_existed else [], "unchanged": [] if changed_map else [f"projects/{project.project_id}/documentation-map.md"]},
        "sync_state": "synchronized", "blockers": [],
    }
    _write_immutable_json(base / "receipts" / f"{project.project_id}-{inventory['inventory_sha256'][:16]}.json", receipt)
    state["last_receipt"] = receipt_id
    ingestion_state.save_state(state_path, state)
    return {"ok": True, "status": "ingested", "project_id": project.project_id, "inventory": inventory, "plan": plan, "counts": counts, "processing": processed, "timings": timings, "coverage": coverage, "conflicts": conflicts, "receipt": receipt}
