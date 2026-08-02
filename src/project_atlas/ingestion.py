"""Deterministic text-native ingestion for the Atlas Core vertical slice."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, NamedTuple

from pydantic import ValidationError

from atlas_contracts.agent_event import SkillBinding
from atlas_contracts.event_package import (
    EventPackage,
    EventPackageInventory,
    PackageValidationError,
    load_event_package,
)
from atlas_contracts.identity import safe_relative_component
from project_atlas.domain.semantic import SourceLifecycleRecord
from project_atlas.domain.sources import SourceRecord
from project_atlas.domain.vocabulary import DocumentLifecycle
from project_atlas.secrets import scan_text
from project_atlas.semantic_compiler import compile_project_record, render_project_record

CLASS_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("architecture", ("architecture", "design")),
    ("validation", ("validation", "test report", "acceptance")),
    ("roadmap", ("roadmap", "plan")),
    ("requirements", ("requirement", "specification")),
    ("work-package", ("work package", "work-package", "wp-")),
    ("security", ("security", "threat model")),
    ("project-overview", ("readme", "overview", "project")),
)


def _classify(path: str, text: str) -> tuple[str, str]:
    haystack = f"{path}\n{text[:4000]}".lower()
    for label, signals in CLASS_RULES:
        if any(signal in haystack for signal in signals):
            return label, "deterministic-path-or-heading"
    return "unknown", "no-deterministic-signal"


def _generated_content(path: Path, content: str) -> str:
    """Render a generated note while preserving its human-owned regions."""
    start = "<!-- atlas:generated:start -->"
    end = "<!-- atlas:generated:end -->"
    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        has_marker = start in existing or end in existing
        if has_marker:
            if existing.count(start) != 1 or existing.count(end) != 1:
                raise ValueError(f"malformed generated markers: {path}")
            start_index = existing.index(start)
            end_index = existing.index(end)
            if end_index < start_index:
                raise ValueError(f"malformed generated markers: {path}")
            generated_start = content.index(start)
            generated_end = content.index(end) + len(end)
            content = (
                existing[:start_index]
                + content[generated_start:generated_end]
                + existing[end_index + len(end):]
            )
    return content


def _promote(plan: dict[Path, bytes]) -> None:
    """Promote a fully validated canonical write plan."""
    for path in sorted(plan):
        _atomic_bytes(path, plan[path])


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == content:
        return
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _validate_existing_markers(vault: Path, project_ids: set[str]) -> None:
    """Preflight all affected project notes before any transaction writes."""
    start = "<!-- atlas:generated:start -->"
    end = "<!-- atlas:generated:end -->"
    for project in sorted(project_ids):
        path = _inside(vault, vault / "projects" / project / "project.md")
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if (start in text or end in text) and (
            text.count(start) != 1
            or text.count(end) != 1
            or text.index(end) < text.index(start)
        ):
            raise ValueError(f"malformed generated markers: {path}")


class _PreparedRecord(NamedTuple):
    source: SourceRecord
    source_path: Path
    destination: Path
    text: str


class _PreparedEvent(NamedTuple):
    package: EventPackage
    destination: Path


def _inside(root: Path, candidate: Path) -> Path:
    """Resolve a candidate and reject paths escaping ``root``."""
    resolved_root = root.resolve()
    resolved_candidate = Path(candidate).resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"destination escapes Vault root: {candidate}") from exc
    return resolved_candidate


def _source_path(root: Path, value: str) -> Path:
    """Resolve a manifest source path without permitting traversal."""
    if not value or Path(value).is_absolute() or "\\" in value:
        raise ValueError(f"unsafe manifest source path: {value!r}")
    parts = Path(value).parts
    if ".." in parts:
        raise ValueError(f"unsafe manifest source path: {value!r}")
    return _inside(root, root / value)


def _manifest_records(manifest: object) -> list[SourceRecord]:
    """Validate the bounded manifest contract at the ingestion boundary."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")
    required = {"schema_version", "source_root", "sources", "duplicates", "inventory_sha256"}
    allowed = required | {"agent_events"}
    if not required.issubset(manifest) or not set(manifest).issubset(allowed):
        raise ValueError("manifest fields do not match schema version 1")
    if manifest["schema_version"] != 1 or not isinstance(manifest["source_root"], str):
        raise ValueError("manifest schema_version or source_root is invalid")
    if not isinstance(manifest["sources"], list) or not isinstance(manifest["duplicates"], dict):
        raise ValueError("manifest sources or duplicates is invalid")
    if not isinstance(manifest["inventory_sha256"], str) or len(manifest["inventory_sha256"]) != 64:
        raise ValueError("manifest inventory_sha256 is invalid")
    records: list[SourceRecord] = []
    for raw in manifest["sources"]:
        if not isinstance(raw, dict):
            raise ValueError("manifest source record must be an object")
        try:
            record = SourceRecord.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(f"invalid manifest source record: {exc}") from exc
        _source_path(Path(str(manifest["source_root"])).resolve(), record.path)
        records.append(record)
    return records


def _manifest_events(manifest: object) -> list[EventPackageInventory]:
    """Validate discovery's event inventory before package loading."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")
    raw_events = manifest.get("agent_events", [])
    if not isinstance(raw_events, list):
        raise ValueError("manifest agent_events must be a list")
    try:
        return [EventPackageInventory.model_validate(raw) for raw in raw_events]
    except ValidationError as exc:
        raise ValueError(f"invalid agent-event inventory: {exc}") from exc


def _vault_identity(vault: Path) -> dict[str, Any] | None:
    """Read the optional logical Vault identity used by event packages."""
    identity_path = vault / ".atlas" / "vault.json"
    if not identity_path.is_file():
        return None
    try:
        raw = json.loads(identity_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Vault identity must be an object")
        return raw
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid Vault identity: {exc}") from exc


def _trusted_skill(vault: Path) -> SkillBinding | None:
    """Load the deployment-provisioned certified skill binding."""
    policy_path = vault / ".atlas" / "agent-event-policy.json"
    if not policy_path.is_file():
        return None
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("agent-event policy must be an object")
        return SkillBinding.model_validate(raw.get("skill"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise ValueError(f"invalid agent-event policy: {exc}") from exc


def _event_link(project: str, event_id: str) -> str:
    return f"../../sources/agent-events/{project}/{event_id}/event.md"


def _event_line(entry: dict[str, str]) -> str:
    package_link = f"[{entry['event_id']}]({entry['source']})"
    work_package = entry.get("work_package_id") or "unknown"
    return (
        f"- {package_link} — `{entry['event_type']}` — session `{entry['session_id']}` — "
        f"work package `{work_package}` — {entry['summary']}"
    )


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _previous_event_state(vault: Path) -> dict[str, list[dict[str, Any]]]:
    state_root = vault / "state" / "agent-events"
    previous: dict[str, list[dict[str, Any]]] = {}
    if not state_root.is_dir():
        return previous
    for path in sorted(state_root.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("events"), list):
                previous[path.stem] = [item for item in raw["events"] if isinstance(item, dict)]
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
    return previous


_LEGACY_SOURCE_CHANGE_VALUES = {
    "new",
    "unchanged",
    "modified",
    "deleted",
    "restored",
    "restored-elsewhere",
    "renamed",
}


def _repair_source_state_item(
    item: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str] | None]:
    candidate = dict(item)
    legacy = candidate.pop("lifecycle", None)
    if legacy is None:
        return candidate, None
    if legacy in _LEGACY_SOURCE_CHANGE_VALUES:
        candidate["document_lifecycle"] = (
            "historical" if legacy in {"deleted", "restored-elsewhere"} else "verified"
        )
        candidate["source_change_state"] = legacy
        candidate["compatibility_repaired"] = True
        candidate["compatibility_repair_reason"] = (
            f"legacy lifecycle value {legacy!r} moved to source_change_state"
        )
        return candidate, {
            "source_id": str(candidate.get("source_id", "")),
            "legacy_value": legacy,
            "source_change_state": legacy,
        }
    if legacy in {value.value for value in DocumentLifecycle}:
        candidate["document_lifecycle"] = legacy
        candidate.setdefault("source_change_state", "unchanged")
        candidate["compatibility_repaired"] = True
        candidate["compatibility_repair_reason"] = (
            "legacy semantic lifecycle field renamed to document_lifecycle"
        )
        return candidate, {
            "source_id": str(candidate.get("source_id", "")),
            "legacy_value": legacy,
            "source_change_state": "unchanged",
        }
    raise ValueError(f"unknown legacy source lifecycle value: {legacy!r}")


def _previous_source_state(
    vault: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    path = vault / "state" / "sources.json"
    if not path.is_file():
        return [], []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ValueError("source lifecycle state schema_version is unsupported")
        values = raw.get("sources")
        if not isinstance(values, list):
            raise ValueError("source lifecycle state sources must be a list")
        records: list[dict[str, Any]] = []
        repairs: list[dict[str, str]] = []
        for item in values:
            if not isinstance(item, dict):
                raise ValueError("source lifecycle records must be objects")
            repaired, repair = _repair_source_state_item(item)
            records.append(SourceLifecycleRecord.model_validate(repaired).model_dump(mode="json"))
            if repair:
                repairs.append(repair)
        return records, repairs
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError) as exc:
        raise ValueError(f"invalid source lifecycle state: {exc}") from exc


def ingest(manifest_path: Path, vault: Path) -> dict[str, Any]:
    """Ingest eligible manifest records and create provenance-backed notes."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = _manifest_records(manifest)
    root = Path(str(manifest["source_root"])).resolve()
    vault = vault.expanduser().resolve()
    expected_vault = _vault_identity(vault)
    expected_skill = _trusted_skill(vault)
    imported: list[dict[str, Any]] = []
    classifications: dict[str, dict[str, str]] = {}
    projects: dict[str, list[dict[str, Any]]] = {}
    event_entries: dict[str, list[dict[str, str]]] = {}
    event_state: dict[str, list[dict[str, Any]]] = {}
    quarantined_events: list[dict[str, Any]] = []
    security_findings: list[dict[str, str]] = []
    write_plan: dict[Path, bytes] = {}
    previous_state = _previous_event_state(vault)
    previous_sources, source_state_repairs = _previous_source_state(vault)
    event_inventories = _manifest_events(manifest)
    prepared: list[_PreparedRecord] = []
    for source_record in sources:
        if source_record.exclusion_reason or not source_record.sha256:
            continue
        source = _source_path(root, source_record.path)
        if not source.is_file():
            raise ValueError(f"manifest source is missing: {source_record.path}")
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise ValueError(f"manifest source is not valid UTF-8: {source_record.path}") from exc
        findings = scan_text(text)
        if findings:
            security_findings.extend(
                {
                    "source_id": source_record.source_id,
                    "path": source_record.path,
                    "pattern": finding.pattern,
                    "confidence": finding.confidence,
                    "hint": finding.redacted_hint,
                }
                for finding in findings
            )
            continue
        supported_suffixes = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".html"}
        suffix = source.suffix.lower() if source.suffix.lower() in supported_suffixes else ".txt"
        destination = _inside(
            vault,
            vault / "sources" / "imported-documents" / f"{source_record.source_id}{suffix}",
        )
        prepared.append(_PreparedRecord(source_record, source, destination, text))
    for source_record, source, destination, text in prepared:
        classification, method = _classify(source_record.path, text)
        source_id = source_record.source_id
        entry: dict[str, str] = {
            "source_id": source_id,
            "path": source_record.path,
            "classification": classification,
            "source": f"../../sources/imported-documents/{destination.name}",
            "sha256": source_record.sha256 or "",
        }
        imported.append(entry)
        classifications[source_id] = {"type": classification, "method": method}
        project = source_record.likely_project or "unknown-project"
        projects.setdefault(project, []).append(entry)
        if not destination.exists():
            write_plan[destination] = source.read_bytes()
    prepared_events: list[_PreparedEvent] = []
    seen_event_ids: dict[str, dict[str, str]] = {}
    for inventory in event_inventories:
        try:
            safe_relative_component(inventory.project_id, label="project_id")
            state_project = inventory.project_id
        except ValueError:
            state_project = "__invalid__"
        state_record: dict[str, Any] = {
            "project_id": inventory.project_id,
            "event_id": inventory.event_id,
            "package_path": inventory.package_path,
            "status": inventory.status,
            "errors": inventory.errors,
        }
        if inventory.status != "valid":
            event_state.setdefault(state_project, []).append(state_record)
            quarantined_events.append(state_record)
            continue
        if expected_vault is None or expected_skill is None:
            state_record["status"] = "rejected"
            state_record["errors"] = [
                reason
                for reason, missing in (
                    ("target Vault identity is unavailable", expected_vault is None),
                    ("trusted agent-event skill policy is unavailable", expected_skill is None),
                )
                if missing
            ]
            event_state.setdefault(state_project, []).append(state_record)
            quarantined_events.append(state_record)
            continue
        try:
            package = load_event_package(
                root, inventory.project_id, inventory.event_id, inventory.package_path
            )
            actual_vault = package.envelope.vault.model_dump(exclude_none=True)
            expected = {
                key: expected_vault[key]
                for key in ("vault_id", "vault_uuid")
                if key in expected_vault
            }
            if any(actual_vault.get(key) != value for key, value in expected.items()):
                raise PackageValidationError(
                    "event package Vault identity does not match target Vault"
                )
            if package.envelope.skill != expected_skill:
                raise PackageValidationError(
                    "event package skill binding does not match trusted skill policy"
                )
        except (PackageValidationError, OSError, ValueError) as exc:
            state_record["status"] = "rejected"
            state_record["errors"] = [str(exc)]
            event_state.setdefault(state_project, []).append(state_record)
            quarantined_events.append(state_record)
            continue
        fingerprint = package.component_sha256
        prior = seen_event_ids.get(package.event_id)
        if prior is not None:
            if prior == fingerprint:
                state_record["status"] = "identical-replay"
            else:
                state_record["status"] = "conflicting-duplicate"
                state_record["errors"] = ["event_id maps to different package content"]
                quarantined_events.append(state_record)
            event_state.setdefault(state_project, []).append(state_record)
            continue
        seen_event_ids[package.event_id] = fingerprint
        destination = _inside(
            vault,
            vault / "sources" / "agent-events" / package.project_id / package.event_id,
        )
        if destination.is_dir():
            existing_hashes = {
                name: _file_hash(destination / name)
                for name in ("event.md", "event.json", "provenance.json", "receipt.yaml")
                if (destination / name).is_file()
            }
            if existing_hashes and existing_hashes != fingerprint:
                state_record["status"] = "changed-source"
                state_record["errors"] = ["event package content changed after prior ingestion"]
                event_state.setdefault(package.project_id, []).append(state_record)
                quarantined_events.append(state_record)
                continue
        prepared_events.append(_PreparedEvent(package, destination))
        event = package.envelope.event
        entry = {
            "event_id": package.event_id,
            "event_type": event.event_type.value,
            "session_id": event.session_id,
            "work_package_id": event.work_package_id or "",
            "summary": event.summary,
            "timestamp": event.timestamp.isoformat(),
            "source": _event_link(package.project_id, package.event_id),
            "receipt_id": package.receipt.receipt_id,
        }
        event_entries.setdefault(package.project_id, []).append(entry)
        event_state.setdefault(package.project_id, []).append(
            {
                "event_id": package.event_id,
                "package_path": package.package_path,
                "status": "accepted",
                "component_sha256": package.component_sha256,
                "receipt_id": package.receipt.receipt_id,
            }
        )
        projects.setdefault(package.project_id, [])
    _validate_existing_markers(vault, set(projects))
    current_event_ids = {
        record["event_id"]
        for records in event_state.values()
        for record in records
        if record.get("status") in {"accepted", "identical-replay"}
    }
    for project, records in previous_state.items():
        for record in records:
            event_id = record.get("event_id")
            if (
                record.get("status") == "accepted"
                and isinstance(event_id, str)
                and event_id not in current_event_ids
            ):
                event_state.setdefault(project, []).append(
                    {
                        "event_id": event_id,
                        "status": "source-missing",
                        "previous": record,
                    }
                )
    for prepared_event in prepared_events:
        package = prepared_event.package
        package_root = prepared_event.destination
        source_package = _inside(root, root / package.package_path)
        for name in sorted(("event.md", "event.json", "provenance.json", "receipt.yaml")):
            destination = _inside(vault, package_root / name)
            if not destination.exists():
                write_plan[destination] = (source_package / name).read_bytes()
        receipt_destination = _inside(
            vault,
            vault / "receipts" / "agent-events" / package.project_id / f"{package.event_id}.yaml",
        )
        write_plan[receipt_destination] = (source_package / "receipt.yaml").read_bytes()
    report = {
        "schema_version": 1,
        "inventory_sha256": manifest.get("inventory_sha256"),
        "classifications": classifications,
        "documents_ingested": len(imported),
        "security_findings": len(security_findings),
        "duplicates": manifest.get("duplicates", {}),
    }
    current_sources: list[dict[str, Any]] = []
    previous_by_id = {str(item.get("source_id")): item for item in previous_sources}
    previous_by_hash = {
        str(item.get("sha256")): item
        for item in previous_sources
        if item.get("sha256")
    }
    for entry in sorted(imported, key=lambda item: str(item["source_id"])):
        source_id = str(entry["source_id"])
        previous = previous_by_id.get(source_id)
        change_state = "new"
        renamed_from = None
        if previous:
            if previous.get("source_change_state") == "deleted":
                change_state = "restored"
            elif previous.get("sha256") != entry["sha256"]:
                change_state = "modified"
            else:
                change_state = "unchanged"
        else:
            same_hash = previous_by_hash.get(str(entry["sha256"]))
            if same_hash:
                change_state = "renamed"
                renamed_from = str(same_hash.get("path"))
        current_sources.append(
            {
                "schema_version": 1,
                "source_id": source_id,
                "path": entry["path"],
                "sha256": entry["sha256"],
                "document_lifecycle": "verified",
                "source_change_state": change_state,
                "first_seen": previous.get("first_seen") if previous else None,
                "last_seen": entry.get("observed_at") or None,
                "previous_sha256": (
                    previous.get("sha256")
                    if previous and previous.get("sha256") != entry["sha256"]
                    else None
                ),
                "renamed_from": renamed_from,
                "restored_as": None,
                "compatibility_repaired": bool(previous and previous.get("compatibility_repaired")),
                "compatibility_repair_reason": (
                    previous.get("compatibility_repair_reason") if previous else None
                ),
            }
        )
    current_ids = {str(item["source_id"]) for item in current_sources}
    current_by_hash = {
        str(item["sha256"]): str(item["source_id"])
        for item in current_sources
        if item.get("sha256")
    }
    for item in current_sources:
        previous = previous_by_id.get(str(item["source_id"]))
        if (
            previous
            and previous.get("sha256") != item.get("sha256")
            and item.get("source_change_state") not in {"restored", "renamed"}
        ):
            item["source_change_state"] = "modified"
            item["previous_sha256"] = previous.get("sha256")
    for previous in previous_sources:
        source_id = str(previous.get("source_id", ""))
        if source_id and source_id not in current_ids:
            restored_id = current_by_hash.get(str(previous.get("sha256")))
            tombstone = dict(previous)
            tombstone["document_lifecycle"] = "historical"
            tombstone["source_change_state"] = (
                "restored-elsewhere" if restored_id else "deleted"
            )
            tombstone["compatibility_repaired"] = False
            tombstone["compatibility_repair_reason"] = None
            if restored_id:
                tombstone["restored_as"] = restored_id
            current_sources.append(tombstone)
    write_plan[_inside(vault, vault / "state" / "sources.json")] = (
        json.dumps(
            {"schema_version": 1, "sources": current_sources}, indent=2, sort_keys=True
        )
        + "\n"
    ).encode()
    if source_state_repairs:
        repair_payload = {
            "schema_version": 1,
            "receipt_type": "source-lifecycle-compatibility-repair",
            "repairs": source_state_repairs,
            "reason": "known legacy lifecycle values were separated from document lifecycle",
        }
        repair_hash = hashlib.sha256(
            json.dumps(repair_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:24]
        write_plan[
            _inside(
                vault,
                vault / "receipts" / "source-lifecycle" / f"repair-{repair_hash}.json",
            )
        ] = (json.dumps(repair_payload, indent=2, sort_keys=True) + "\n").encode()
    write_plan[_inside(vault, vault / "sources" / "manifests" / "source-manifest.json")] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
    write_plan[_inside(vault, vault / "generated" / "reports" / "ingestion-report.json")] = (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    ).encode()
    write_plan[_inside(vault, vault / "generated" / "reports" / "secret-findings.json")] = (
        json.dumps(security_findings, indent=2, sort_keys=True) + "\n"
    ).encode()
    if quarantined_events:
        write_plan[_inside(vault, vault / "quarantine" / "agent-events" / "index.json")] = (
            json.dumps(quarantined_events, indent=2, sort_keys=True) + "\n"
        ).encode()
    for project, records in sorted(event_state.items()):
        write_plan[_inside(vault, vault / "state" / "agent-events" / f"{project}.json")] = (
            json.dumps(
                {"schema_version": 1, "project_id": project, "events": records},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode()
    for project, entries in sorted(projects.items()):
        project_record = compile_project_record(project, entries, event_entries.get(project, []))
        project_root = _inside(vault, vault / "projects" / project)
        project_path = _inside(vault, project_root / "project.md")
        write_plan[project_path] = _generated_content(
            project_path, render_project_record(project_record, entries)
        ).encode()
        map_lines = [
            f"# Documentation map — {project}", "", "| Source | Classification | SHA-256 |",
            "|---|---|---|",
        ]
        for entry in sorted(entries, key=lambda item: str(item["path"]).lower()):
            map_lines.append(
                f"| [{entry['path']}]({entry['source']}) | "
                f"{entry['classification']} | `{entry['sha256']}` |"
            )
        write_plan[_inside(vault, project_root / "documentation-map.md")] = (
            "\n".join(map_lines) + "\n"
        ).encode()
        project_events = sorted(
            event_entries.get(project, []), key=lambda item: (item["timestamp"], item["event_id"])
        )
        event_projections = {
            "activity": project_events,
            "sessions": project_events,
            "validations": [e for e in project_events if e["event_type"] == "validation"],
            "decisions": [e for e in project_events if e["event_type"] == "decision"],
            "blockers": [
                e for e in project_events if e["event_type"] in {"blocker", "failure"}
            ],
            "work-packages": [e for e in project_events if e["work_package_id"]],
        }
        for name, selected in event_projections.items():
            title = name.replace("-", " ").title()
            lines = [f"# {title} — {project}", ""]
            if selected:
                lines.extend(_event_line(entry) for entry in selected)
            else:
                lines.append("_No verified agent events in this category._")
            write_plan[_inside(vault, project_root / f"{name}.md")] = (
                "\n".join(lines) + "\n"
            ).encode()
    _promote(write_plan)
    return {
        "ok": True,
        "projects": len(projects),
        "documents_ingested": len(imported),
        "events_ingested": len(prepared_events),
        "events_quarantined": len(quarantined_events),
        "security_findings": len(security_findings),
        "inventory_sha256": manifest.get("inventory_sha256"),
    }
