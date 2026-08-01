"""Strict validation for AS-WP-004 machine and human artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class IngestionValidationReport:
    project_id: str
    documents_checked: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "project_id": self.project_id, "documents_checked": self.documents_checked, "errors": self.errors, "warnings": self.warnings}


def validate(vault_root: Path, project_id: str) -> IngestionValidationReport:
    report = IngestionValidationReport(project_id)
    base = vault_root / "ingestion"
    inventory_path = base / "inventory" / f"{project_id}.json"
    state_path = base / "state" / f"{project_id}.json"
    if not inventory_path.is_file():
        report.errors.append(f"missing inventory: {inventory_path}")
        return report
    if not state_path.is_file():
        report.errors.append(f"missing ingestion state: {state_path}")
        return report
    import json
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    for item in inventory.get("documents", []):
        report.documents_checked += 1
        if not item.get("document_id", "").startswith(f"{project_id}:"):
            report.errors.append(f"invalid document id: {item.get('document_id')}")
        if item.get("processing", {}).get("state") not in {"discovered", "unsupported", "sensitive", "failed"}:
            report.warnings.append(f"unexpected inventory state: {item.get('document_id')}")
    if state.get("project_id") != project_id:
        report.errors.append("state project_id mismatch")
    if not (vault_root / "projects" / project_id / "documentation-map.md").is_file():
        report.errors.append("missing documentation-map.md projection")
    receipts = sorted((base / "receipts").glob(f"{project_id}-*.json"))
    if not receipts:
        report.errors.append("missing ingestion receipt")
    return report
