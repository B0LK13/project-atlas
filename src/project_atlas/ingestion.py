"""Deterministic text-native ingestion for the Atlas Core vertical slice."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import ExitStack, suppress
from pathlib import Path
from typing import Any, NamedTuple

import yaml
from pydantic import ValidationError

from atlas_contracts.agent_event import SkillBinding
from atlas_contracts.event_package import (
    EventPackage,
    EventPackageInventory,
    PackageValidationError,
    load_event_package,
)
from atlas_contracts.identity import safe_relative_component
from project_atlas.compilation import (
    CompilationCandidate,
    CompilationOutcome,
    validate_compilation_transition,
)
from project_atlas.domain import (
    CanonicalImpact,
    Diagnostic,
    DiagnosticCode,
    Severity,
)
from project_atlas.domain.semantic import SourceLifecycleRecord
from project_atlas.domain.source_registry import SourceLineageRecord
from project_atlas.domain.sources import SourceRecord
from project_atlas.domain.vocabulary import DocumentLifecycle, SourceChangeState
from project_atlas.graph_acceptance import classify_graphify_document
from project_atlas.knowledge_compiler import compile_knowledge, render_bundle
from project_atlas.lineage import (
    build_project_registry,
    migrate_v1_records_with_receipts,
)
from project_atlas.quarantine import scan_text as scan_injection
from project_atlas.schema import validate_record
from project_atlas.secrets import scan_text
from project_atlas.semantic_compiler import compile_project_record, render_project_record
from project_atlas.source_identity import (
    ProjectIdentityLock,
    ProjectUuidProvider,
    canonical_source_sha256,
    production_project_uuid,
    validate_project_uuid,
)

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
    # AS-GRAPH-001: Graphify artifact basenames classify as derived graphify-output
    # before keyword rules so architecture/design tokens cannot elevate them.
    graphify_type = classify_graphify_document(path)
    if graphify_type is not None:
        return graphify_type, "deterministic-graphify-basename"
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


class _PromotionEntry(NamedTuple):
    path: Path
    staged: Path
    backup: Path
    had_original: bool


def _replace_path(source: Path, destination: Path) -> None:
    """Small seam for atomic-promotion fault injection tests."""
    os.replace(source, destination)


def _remove_empty_directories(directories: set[Path]) -> None:
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        with suppress(OSError):
            directory.rmdir()


def _promotion_failure_report_path(vault: Path) -> Path:
    return _inside(vault, vault / "quarantine" / "promotion-failures" / "index.json")


def _quarantine_promotion_failure(
    vault: Path,
    project_candidates: dict[str, tuple[CompilationCandidate, ...]],
    error: BaseException,
) -> None:
    """Record §7.8 PROMOTION_FAILED outcomes when canonical promotion fails.

    Canonical state is untouched — the cross-file rollback inside `_promote`
    stays authoritative. This quarantine report is diagnostic evidence only
    and is best-effort: a reporting failure never masks the promotion error.
    Promotable candidates transition through the governed §7.8 edges
    COMPLETE_CANDIDATE -> PROMOTING -> PROMOTION_FAILED.
    """
    try:
        projects: list[dict[str, Any]] = []
        for project, candidates in sorted(project_candidates.items()):
            recorded: list[dict[str, Any]] = []
            for candidate in candidates:
                outcome = candidate.outcome
                if candidate.promotable:
                    validate_compilation_transition(
                        CompilationOutcome.COMPLETE_CANDIDATE, CompilationOutcome.PROMOTING
                    )
                    validate_compilation_transition(
                        CompilationOutcome.PROMOTING, CompilationOutcome.PROMOTION_FAILED
                    )
                    outcome = CompilationOutcome.PROMOTION_FAILED
                recorded.append(
                    {
                        "source_path": candidate.source_path,
                        "outcome": outcome.value,
                        "claims_extracted": candidate.claims_extracted,
                        "claims_withheld": candidate.claims_withheld,
                        "diagnostics": sorted(candidate.diagnostics),
                    }
                )
            projects.append({"project_id": project, "candidates": recorded})
        diagnostic = Diagnostic(
            code=DiagnosticCode.PROMOTION_FAILURE,
            severity=Severity.ERROR,
            parser="canonical-promotion",
            reason=(
                f"canonical promotion failed and rolled back: "
                f"{type(error).__name__}: {error}"
            ),
            remediation=(
                "resolve the promotion fault and re-run ingestion; canonical "
                "state is unchanged"
            ),
            continued=False,
            canonical_impact=CanonicalImpact.BLOCKED,
        )
        validate_record(diagnostic, "diagnostic")
        payload = {
            "schema_version": 1,
            "receipt_type": "promotion-failure",
            "projects": projects,
            "diagnostics": [diagnostic.model_dump(mode="json")],
        }
        path = _promotion_failure_report_path(vault)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass  # never mask the promotion failure itself


def _clear_promotion_failure_report(vault: Path) -> None:
    """Remove a stale promotion-failure quarantine report after success."""
    path = _promotion_failure_report_path(vault)
    if path.is_file():
        path.unlink()
        _remove_empty_directories({path.parent})


def _promote(plan: dict[Path, bytes]) -> None:
    """Promote a validated write plan with cross-file rollback.

    Every changed file is staged before canonical state is touched. Existing
    files are moved to transaction-scoped backups during promotion. Any
    mid-promotion failure restores every prior target and removes all staging
    artifacts before the error escapes.
    """
    transaction = uuid.uuid4().hex
    entries: list[_PromotionEntry] = []
    created_directories: set[Path] = set()
    try:
        for path in sorted(plan):
            parent = path.parent
            while not parent.exists():
                created_directories.add(parent)
                parent = parent.parent
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and not path.is_file():
                raise IsADirectoryError(f"canonical write target is not a file: {path}")
            if path.is_file() and path.read_bytes() == plan[path]:
                continue
            staged = path.with_name(f".{path.name}.{transaction}.atlas-stage")
            backup = path.with_name(f".{path.name}.{transaction}.atlas-backup")
            staged.write_bytes(plan[path])
            entries.append(
                _PromotionEntry(
                    path=path,
                    staged=staged,
                    backup=backup,
                    had_original=path.exists(),
                )
            )
    except BaseException:
        for entry in entries:
            entry.staged.unlink(missing_ok=True)
            entry.backup.unlink(missing_ok=True)
        _remove_empty_directories(created_directories)
        raise

    touched: list[_PromotionEntry] = []
    try:
        for entry in entries:
            if entry.had_original:
                _replace_path(entry.path, entry.backup)
            touched.append(entry)
            _replace_path(entry.staged, entry.path)
    except BaseException as promotion_error:
        rollback_errors: list[BaseException] = []
        for entry in reversed(touched):
            try:
                if entry.had_original:
                    _replace_path(entry.backup, entry.path)
                else:
                    entry.path.unlink(missing_ok=True)
            except BaseException as exc:  # pragma: no cover - catastrophic filesystem loss
                rollback_errors.append(exc)
        if rollback_errors:
            raise RuntimeError(
                "canonical promotion failed and rollback was incomplete; "
                "transaction artifacts were preserved for recovery"
            ) from promotion_error
        for entry in entries:
            entry.staged.unlink(missing_ok=True)
            entry.backup.unlink(missing_ok=True)
        _remove_empty_directories(created_directories)
        raise

    for entry in entries:
        entry.staged.unlink(missing_ok=True)
        entry.backup.unlink(missing_ok=True)


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
        if not isinstance(raw, dict) or raw.get("schema_version") not in {1, 2}:
            raise ValueError("source lifecycle state schema_version is unsupported")
        values = raw.get("sources")
        if not isinstance(values, list):
            raise ValueError("source lifecycle state sources must be a list")
        records: list[dict[str, Any]] = []
        repairs: list[dict[str, str]] = []
        for item in values:
            if not isinstance(item, dict):
                raise ValueError("source lifecycle records must be objects")
            if raw.get("schema_version") == 2:
                record = {
                    "schema_version": 1,
                    "source_id": item.get("source_id"),
                    "path": item.get("current_path"),
                    "sha256": item.get("current_content_sha256"),
                    "document_lifecycle": item.get("document_lifecycle", "verified"),
                    "source_change_state": item.get("source_change_state", "unchanged"),
                    "renamed_from": item.get("renamed_from"),
                    "restored_as": item.get("restored_as"),
                    "compatibility_repaired": False,
                    "compatibility_repair_reason": None,
                }
                records.append(record)
                continue
            if "current_path" in item or "current_content_sha256" in item:
                item = {
                    "source_id": item.get("source_id"),
                    "path": item.get("current_path"),
                    "sha256": item.get("current_content_sha256"),
                    "document_lifecycle": item.get("document_lifecycle", "verified"),
                    "source_change_state": item.get("source_change_state", "unchanged"),
                    "lifecycle": item.get("lifecycle"),
                    "compatibility_repaired": item.get("compatibility_repaired", False),
                    "compatibility_repair_reason": item.get("compatibility_repair_reason"),
                }
            repaired, repair = _repair_source_state_item(item)
            records.append(SourceLifecycleRecord.model_validate(repaired).model_dump(mode="json"))
            if repair:
                repairs.append(repair)
        return records, repairs
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError) as exc:
        raise ValueError(f"invalid source lifecycle state: {exc}") from exc


def _find_project_marker(root: Path, relative_path: str, project: str) -> Path:
    current = _source_path(root, relative_path).parent
    while True:
        for marker in (current / ".atlas-project.yaml", current / ".atlas" / "project.yaml"):
            if marker.is_file() and not marker.is_symlink():
                try:
                    raw = yaml.safe_load(marker.read_text(encoding="utf-8")) or {}
                except (OSError, UnicodeError, yaml.YAMLError) as exc:
                    raise ValueError(f"invalid project marker: {marker}") from exc
                project_data = raw.get("project") if isinstance(raw, dict) else None
                marker_project = (
                    project_data.get("id") if isinstance(project_data, dict) else None
                )
                if marker_project == project:
                    return marker
        if current == root or current.parent == current:
            break
        current = current.parent
    raise ValueError(f"project marker not found for project: {project}")


def _project_context(root: Path, relative_path: str, project: str) -> dict[str, str]:
    """Read optional concept metadata from the authoritative project marker."""
    try:
        marker = _find_project_marker(root, relative_path, project)
    except ValueError as exc:
        if str(exc).startswith("project marker not found for project:"):
            return {}
        raise
    try:
        raw = yaml.safe_load(marker.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid project marker: {marker}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"project marker must be an object: {marker}")
    concept_type = raw.get("concept_type")
    if concept_type is None:
        return {}
    if not isinstance(concept_type, str) or not concept_type.strip():
        raise ValueError(f"project marker concept_type must be a non-empty string: {marker}")
    return {"concept_type": concept_type}


def _prepare_project_identity(
    root: Path,
    vault: Path,
    project: str,
    relative_path: str,
    uuid_provider: ProjectUuidProvider,
    write_plan: dict[Path, bytes],
) -> tuple[str, Path, bytes, bool]:
    """Prepare an immutable project UUID marker mutation inside the plan."""
    marker = _find_project_marker(root, relative_path, project)
    original = marker.read_bytes()
    try:
        data = yaml.safe_load(original.decode("utf-8")) or {}
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid project marker: {marker}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"project marker must be an object: {marker}")
    raw_uuid = data.get("project_uuid")
    allocated = raw_uuid is None
    if allocated:
        project_uuid = validate_project_uuid(uuid_provider())
        data["project_uuid"] = project_uuid
        updated = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).encode("utf-8")
        write_plan[marker] = updated
        receipt = vault / "receipts" / "source-lineage" / f"project-{project}-allocation.json"
        if receipt.is_file():
            raise ValueError(f"project UUID allocation receipt already exists: {receipt}")
        write_plan[receipt] = (
            json.dumps(
                {
                    "schema_version": 1,
                    "receipt_type": "project-identity-allocation",
                    "project": project,
                    "project_uuid": project_uuid,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    else:
        project_uuid = validate_project_uuid(str(raw_uuid))
    return project_uuid, marker, original, allocated


def _assert_state_compare_and_swap(preconditions: dict[Path, bytes | None]) -> None:
    for path, expected in preconditions.items():
        if expected is None:
            if path.is_file():
                raise ValueError(f"state changed during transaction: {path}")
            continue
        if not path.is_file() or path.read_bytes() != expected:
            raise ValueError(f"state changed during transaction: {path}")


def _verify_identity_post_state(
    vault: Path,
    project_identity: dict[str, str],
    markers: dict[str, Path],
    allocated_projects: set[str],
) -> None:
    """Verify promoted identity state while the project lock is still held."""
    registry_path = vault / "state" / "sources.json"
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("post-promotion source registry cannot be reread") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 2:
        raise ValueError("post-promotion source registry schema mismatch")
    values = raw.get("sources")
    if not isinstance(values, list):
        raise ValueError("post-promotion source registry records are invalid")
    parsed: list[SourceLineageRecord] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("post-promotion source registry record is invalid")
        record = SourceLineageRecord.model_validate(value)
        validate_record(record, "source-registry")
        parsed.append(record)
    lineage_ids = [record.source_lineage_id for record in parsed]
    if len(lineage_ids) != len(set(lineage_ids)):
        raise ValueError("post-promotion source registry has conflicting lineage IDs")
    for project, project_uuid in project_identity.items():
        marker = markers[project]
        try:
            marker_data = yaml.safe_load(marker.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ValueError(f"post-promotion project marker cannot be reread: {marker}") from exc
        if not isinstance(marker_data, dict) or validate_project_uuid(
            str(marker_data.get("project_uuid"))
        ) != project_uuid:
            raise ValueError(f"post-promotion project UUID mismatch: {project}")
        project_records = [
            record for record in parsed if record.canonical_project_id == project_uuid
        ]
        if not project_records:
            raise ValueError(f"post-promotion registry has no records for project: {project}")
        allocation_receipts = list(
            (vault / "receipts" / "source-lineage").glob(
                f"project-{project}-allocation.json"
            )
        )
        if project in allocated_projects and len(allocation_receipts) != 1:
            raise ValueError(f"post-promotion allocation receipt count mismatch: {project}")
        if allocation_receipts:
            receipt = json.loads(allocation_receipts[0].read_text(encoding="utf-8"))
            if receipt.get("project_uuid") != project_uuid:
                raise ValueError(f"post-promotion allocation receipt identity mismatch: {project}")


def _read_registry_version(vault: Path) -> int:
    path = vault / "state" / "sources.json"
    if not path.is_file():
        return 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid source registry: {path}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("schema_version"), int):
        raise ValueError(f"invalid source registry: {path}")
    return int(raw["schema_version"])


def _read_registry_records(vault: Path) -> list[dict[str, Any]]:
    path = vault / "state" / "sources.json"
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    values = raw.get("sources") if isinstance(raw, dict) else None
    if not isinstance(values, list):
        raise ValueError(f"invalid source registry: {path}")
    records: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        record = dict(item)
        record.pop("path", None)
        record.pop("sha256", None)
        record.pop("compatibility_repaired", None)
        record.pop("compatibility_repair_reason", None)
        records.append(record)
    return records


def _read_registry_compatibility(vault: Path) -> dict[str, tuple[bool, str | None]]:
    path = vault / "state" / "sources.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    values = raw.get("sources") if isinstance(raw, dict) else None
    if not isinstance(values, list):
        return {}
    return {
        str(item["source_id"]): (
            bool(item.get("compatibility_repaired")),
            item.get("compatibility_repair_reason"),
        )
        for item in values
        if isinstance(item, dict) and item.get("source_id")
    }


# AS-INGEST-MANIFEST-001: multi-batch discovery snapshot / report merge.
_DELETED_SOURCE_CHANGE_STATES = frozenset({"deleted", "restored-elsewhere"})


def _load_vault_json(path: Path) -> Any | None:
    """Best-effort JSON load for prior vault artifacts; missing/invalid → None."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _batch_deleted_source_ids(
    registry_records: list[dict[str, Any]],
    batch_project_uuids: set[str],
) -> set[str]:
    """Return source_ids tombstoned for projects included in the current batch.

    Deletion authority is registry lifecycle for batch projects only
    (AS-INGEST-MANIFEST-001). Projects absent from the batch retain their
    prior snapshot rows even when omitted from the current discover root.
    """
    deleted: set[str] = set()
    if not batch_project_uuids:
        return deleted
    for item in registry_records:
        if str(item.get("canonical_project_id", "")) not in batch_project_uuids:
            continue
        if str(item.get("source_change_state", "")) not in _DELETED_SOURCE_CHANGE_STATES:
            continue
        source_id = str(item.get("source_id", ""))
        if source_id:
            deleted.add(source_id)
    return deleted


def _recompute_duplicates(sources: list[dict[str, Any]]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for record in sources:
        digest = record.get("sha256")
        source_id = record.get("source_id")
        if isinstance(digest, str) and isinstance(source_id, str) and source_id:
            groups.setdefault(digest, []).append(source_id)
    return {
        digest: sorted(ids)
        for digest, ids in sorted(groups.items())
        if len(ids) > 1
    }


def merge_discovery_manifest(
    prior: dict[str, Any] | None,
    incoming: dict[str, Any],
    *,
    deleted_source_ids: set[str],
) -> dict[str, Any]:
    """Upsert discovery snapshot rows by ``source_id`` (AS-INGEST-MANIFEST-001).

    ``source_root`` and ``agent_events`` follow the last batch. ``inventory_sha256``
    is recomputed from the merged semantic payload; ``last_batch_inventory_sha256``
    preserves the incoming batch hash for operators.
    """
    prior_sources = (
        [item for item in prior.get("sources", []) if isinstance(item, dict)]
        if isinstance(prior, dict)
        else []
    )
    incoming_sources = [
        item for item in incoming.get("sources", []) if isinstance(item, dict)
    ]
    by_id: dict[str, dict[str, Any]] = {}
    for item in prior_sources:
        source_id = str(item.get("source_id", ""))
        if not source_id or source_id in deleted_source_ids:
            continue
        by_id[source_id] = dict(item)
    for item in incoming_sources:
        source_id = str(item.get("source_id", ""))
        if not source_id or source_id in deleted_source_ids:
            continue
        by_id[source_id] = dict(item)
    merged_sources = [by_id[key] for key in sorted(by_id)]
    duplicates = _recompute_duplicates(merged_sources)
    prior_version = int(prior.get("schema_version", 1)) if isinstance(prior, dict) else 1
    incoming_version = int(incoming.get("schema_version", 1))
    semantic = {
        "schema_version": max(prior_version, incoming_version, 1),
        "source_root": incoming.get("source_root"),
        "sources": merged_sources,
        "duplicates": duplicates,
        "agent_events": list(incoming.get("agent_events", [])),
    }
    inventory_sha256 = hashlib.sha256(
        json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        **semantic,
        "inventory_sha256": inventory_sha256,
        "last_batch_inventory_sha256": incoming.get("inventory_sha256"),
    }


def merge_ingestion_report(
    prior: dict[str, Any] | None,
    current: dict[str, Any],
    *,
    merged_manifest: dict[str, Any],
    deleted_source_ids: set[str],
) -> dict[str, Any]:
    """Merge classification maps by ``source_id``; keep batch operational counts."""
    active_ids = {
        str(item["source_id"])
        for item in merged_manifest.get("sources", [])
        if isinstance(item, dict) and item.get("source_id")
    }
    classifications: dict[str, Any] = {}
    if isinstance(prior, dict) and isinstance(prior.get("classifications"), dict):
        for source_id, info in prior["classifications"].items():
            key = str(source_id)
            if key in deleted_source_ids or key not in active_ids:
                continue
            classifications[key] = info
    if isinstance(current.get("classifications"), dict):
        for source_id, info in current["classifications"].items():
            key = str(source_id)
            if key in deleted_source_ids or key not in active_ids:
                continue
            classifications[key] = info
    return {
        "schema_version": 1,
        "inventory_sha256": merged_manifest.get("inventory_sha256"),
        "classifications": classifications,
        "documents_ingested": current.get("documents_ingested", 0),
        "security_findings": current.get("security_findings", 0),
        "injection_findings": current.get("injection_findings", 0),
        "duplicates": merged_manifest.get("duplicates", {}),
    }


def merge_secret_findings(
    prior: list[dict[str, Any]] | None,
    current: list[dict[str, Any]],
    *,
    deleted_source_ids: set[str],
    active_source_ids: set[str],
) -> list[dict[str, Any]]:
    """Upsert secret findings by (source_id, pattern)."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for item in (*(prior or ()), *current):
        source_id = str(item.get("source_id", ""))
        pattern = str(item.get("pattern", ""))
        if (
            not source_id
            or source_id in deleted_source_ids
            or source_id not in active_source_ids
        ):
            continue
        merged[(source_id, pattern)] = dict(item)
    return [merged[key] for key in sorted(merged)]


def merge_injection_findings(
    prior: dict[str, Any] | list[dict[str, Any]] | None,
    current_findings: list[dict[str, Any]],
    *,
    deleted_source_ids: set[str],
    active_source_ids: set[str],
) -> list[dict[str, Any]]:
    """Upsert injection findings by (source_id, rule)."""
    prior_findings: list[dict[str, Any]]
    if isinstance(prior, dict) and isinstance(prior.get("findings"), list):
        prior_findings = [item for item in prior["findings"] if isinstance(item, dict)]
    elif isinstance(prior, list):
        prior_findings = [item for item in prior if isinstance(item, dict)]
    else:
        prior_findings = []
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for item in (*prior_findings, *current_findings):
        source_id = str(item.get("source_id", ""))
        rule = str(item.get("rule", ""))
        if (
            not source_id
            or source_id in deleted_source_ids
            or source_id not in active_source_ids
        ):
            continue
        merged[(source_id, rule)] = dict(item)
    return [merged[key] for key in sorted(merged)]


def _ingest(
    manifest_path: Path,
    vault: Path,
    *,
    uuid_provider: ProjectUuidProvider = production_project_uuid,
) -> dict[str, Any]:
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
    injection_findings: list[dict[str, Any]] = []
    write_plan: dict[Path, bytes] = {}
    previous_state = _previous_event_state(vault)
    registry_version = _read_registry_version(vault)
    previous_registry = _read_registry_records(vault) if registry_version == 2 else []
    previous_compatibility = _read_registry_compatibility(vault)
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
        secret_findings = scan_text(text)
        if secret_findings:
            security_findings.extend(
                {
                    "source_id": source_record.source_id,
                    "path": source_record.path,
                    "pattern": finding.pattern,
                    "confidence": finding.confidence,
                    "hint": finding.redacted_hint,
                }
                for finding in secret_findings
            )
            continue
        injection_findings_list = scan_injection(text)
        if injection_findings_list:
            injection_findings.extend(
                {
                    "source_id": source_record.source_id,
                    "path": source_record.path,
                    "source_lineage_id": None,
                    "project_uuid": None,
                    "rule": finding.rule,
                    "confidence": finding.confidence,
                    "hint": finding.redacted_hint,
                    "disposition": "quarantined",
                }
                for finding in injection_findings_list
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
        project = source_record.likely_project or "unknown-project"
        entry: dict[str, Any] = {
            "source_id": source_id,
            "source_lineage_id": source_record.source_lineage_id or "",
            "path": source_record.path,
            "classification": classification,
            "source": f"../../sources/imported-documents/{destination.name}",
            "sha256": source_record.sha256 or "",
            "text": text,
        }
        entry.update(_project_context(root, source_record.path, project))
        if source_record.lineage_resolution is not None:
            entry["lineage_resolution"] = source_record.lineage_resolution.model_dump(mode="json")
        imported.append(entry)
        classifications[source_id] = {"type": classification, "method": method}
        projects.setdefault(project, []).append(entry)
        source_bytes = source.read_bytes()
        manifest_hash = canonical_source_sha256(source)
        # A project-UUID allocation may update the marker after discovery.  Do
        # not copy that stale-manifest mutation as a source observation; the
        # next discovery will carry the authoritative hash.
        source_matches_manifest = manifest_hash == str(source_record.sha256)
        if (source_matches_manifest or source_record.path != ".atlas-project.yaml") and (
            not destination.exists() or destination.read_bytes() != source_bytes
        ):
            write_plan[destination] = source_bytes
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
            "component_sha256": package.component_sha256,
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
    project_identity: dict[str, str] = {}
    marker_preconditions: dict[Path, bytes | None] = {}
    identity_markers: dict[str, Path] = {}
    allocated_projects: set[str] = set()
    for project, entries in sorted(projects.items()):
        if not entries or project == "unknown-project":
            continue
        try:
            project_uuid, marker, original_marker, _allocated = _prepare_project_identity(
                root, vault, project, str(entries[0]["path"]), uuid_provider, write_plan
            )
        except ValueError as exc:
            # Preserve ingestion of legacy hand-authored manifests that predate
            # the project-marker contract. They cannot receive durable identity
            # until a marker is supplied, so no identity is fabricated here.
            if not str(exc).startswith("project marker not found for project:"):
                raise
            continue
        project_identity[project] = project_uuid
        marker_preconditions[marker] = original_marker
        identity_markers[project] = marker
        if _allocated:
            allocated_projects.add(project)
    by_uuid: dict[str, list[str]] = {}
    for project, project_uuid in project_identity.items():
        by_uuid.setdefault(project_uuid, []).append(project)
    duplicate_uuids = {
        project_uuid: owners
        for project_uuid, owners in by_uuid.items()
        if len(owners) > 1
    }
    if duplicate_uuids:
        raise ValueError(
            "duplicate active project_uuid values: "
            + ", ".join(
                f"{project_uuid} ({', '.join(sorted(owners))})"
                for project_uuid, owners in sorted(duplicate_uuids.items())
            )
        )
    previous_by_source_id = {
        str(item.get("source_id")): str(item.get("canonical_project_id"))
        for item in previous_registry
        if item.get("source_id") and item.get("canonical_project_id")
    }
    for project, entries in sorted(projects.items()):
        resolved_uuid = project_identity.get(project)
        if resolved_uuid is None:
            continue
        source_ids = {str(entry["source_id"]) for entry in entries}
        prior_uuids = {
            previous_by_source_id[source_id]
            for source_id in source_ids
            if source_id in previous_by_source_id
        }
        if prior_uuids and prior_uuids != {resolved_uuid}:
            raise ValueError(
                f"project_uuid changed for existing source records in project: {project}"
            )
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
        "injection_findings": len(injection_findings),
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
    registry_records: list[dict[str, Any]] = []
    lineage_migration_receipts: list[dict[str, Any]] = []
    for project, entries in sorted(projects.items()):
        registry_project_uuid = project_identity.get(project)
        if registry_project_uuid is None or not entries:
            continue
        if registry_version == 1:
            prior_for_project, migration_receipts = migrate_v1_records_with_receipts(
                previous_sources, registry_project_uuid
            )
            lineage_migration_receipts.extend(migration_receipts)
        else:
            prior_for_project = [
                item
                for item in previous_registry
                if item.get("canonical_project_id") == registry_project_uuid
            ]
        registry_records.extend(
            build_project_registry(registry_project_uuid, entries, prior_for_project)
        )
    retained_projects = {
        str(item.get("canonical_project_id"))
        for item in registry_records
        if item.get("canonical_project_id")
    }
    registry_records.extend(
        item
        for item in previous_registry
        if str(item.get("canonical_project_id")) not in retained_projects
    )
    registry_records = [
        {
            **item,
            "path": item.get("current_path"),
            "sha256": item.get("current_content_sha256"),
            "compatibility_repaired": (
                str(item.get("source_id"))
                in {str(repair.get("source_id")) for repair in source_state_repairs}
                or previous_compatibility.get(str(item.get("source_id")), (False, None))[0]
            ),
            "compatibility_repair_reason": next(
                (
                    str(repair.get("legacy_value"))
                    for repair in source_state_repairs
                    if str(repair.get("source_id")) == str(item.get("source_id"))
                ),
                previous_compatibility.get(str(item.get("source_id")), (False, None))[1],
            ),
        }
        for item in registry_records
    ]
    # Bind semantic extraction to the durable registry identity before any
    # claim-bearing records are compiled.  The compatibility source_id remains
    # descriptive, but source_lineage_id is the authoritative namespace.
    registry_by_source_id: dict[str, dict[str, Any]] = {}
    for item in registry_records:
        source_id = str(item.get("source_id", ""))
        if not source_id or not item.get("source_lineage_id"):
            continue
        prior = registry_by_source_id.get(source_id)
        if prior is None or (
            str(item.get("source_change_state")) not in {"deleted", "historical"}
            and str(prior.get("source_change_state")) in {"deleted", "historical"}
        ) or (
            str(item.get("source_change_state")) not in {"deleted", "historical"}
            and str(prior.get("source_change_state")) not in {"deleted", "historical"}
            and int(item.get("lineage_generation", 0)) > int(prior.get("lineage_generation", 0))
        ):
            registry_by_source_id[source_id] = item
    for project_entries in projects.values():
        for entry in project_entries:
            lineage_record: dict[str, Any] | None = registry_by_source_id.get(
                str(entry.get("source_id"))
            )
            if lineage_record is not None:
                entry["source_lineage_id"] = str(lineage_record["source_lineage_id"])
                entry["project_uuid"] = str(lineage_record["canonical_project_id"])
                entry["lineage_generation"] = int(lineage_record["lineage_generation"])
    previous_registry_by_source_id = {
        str(item.get("source_id", "")): item
        for item in previous_registry
        if item.get("source_id")
    }
    for finding in injection_findings:
        source_id = str(finding.get("source_id", ""))
        lineage_record = registry_by_source_id.get(source_id)
        if lineage_record is not None:
            finding["source_lineage_id"] = str(lineage_record["source_lineage_id"])
            finding["project_uuid"] = str(lineage_record["canonical_project_id"])
            continue
        prior_record = previous_registry_by_source_id.get(source_id)
        if prior_record is not None:
            finding["source_lineage_id"] = str(prior_record.get("source_lineage_id", "")) or None
            finding["project_uuid"] = str(prior_record.get("canonical_project_id", "")) or None
    generation_receipts: list[dict[str, Any]] = []
    restoration_receipts: list[dict[str, Any]] = []
    previous_by_lineage = {
        str(item.get("source_lineage_id")): item for item in previous_registry
    }
    for item in registry_records:
        if (
            item.get("supersedes_lineage")
            and str(item.get("source_lineage_id")) not in previous_by_lineage
        ):
            generation_receipts.append(
                {
                    "schema_version": 1,
                    "receipt_type": "source-lineage-generation-allocation",
                    "project_uuid": item.get("canonical_project_id"),
                    "source_lineage_id": item.get("source_lineage_id"),
                    "lineage_generation": item.get("lineage_generation"),
                    "supersedes_lineage": item.get("supersedes_lineage"),
                    "current_path": item.get("current_path"),
                    "current_content_sha256": item.get("current_content_sha256"),
                }
            )
        if item.get("source_change_state") not in {
            SourceChangeState.RESTORED.value,
            SourceChangeState.RESTORED_ELSEWHERE.value,
        }:
            continue
        prior = previous_by_lineage.get(str(item.get("source_lineage_id")))
        if prior is not None and (
            prior.get("current_path") == item.get("current_path")
            and prior.get("current_content_sha256") == item.get("current_content_sha256")
            and prior.get("source_change_state")
            in {SourceChangeState.RESTORED.value, SourceChangeState.RESTORED_ELSEWHERE.value}
        ):
            continue
        restoration_receipts.append(
            {
                "schema_version": 1,
                "receipt_type": "source-lineage-restoration",
                "project_uuid": item.get("canonical_project_id"),
                "source_lineage_id": item.get("source_lineage_id"),
                "lineage_generation": item.get("lineage_generation"),
                "source_change_state": item.get("source_change_state"),
                "restored_as": item.get("restored_as"),
                "previous_path": prior.get("current_path") if prior else None,
                "current_path": item.get("current_path"),
                "previous_content_sha256": prior.get("current_content_sha256") if prior else None,
                "current_content_sha256": item.get("current_content_sha256"),
            }
        )
    write_plan[_inside(vault, vault / "state" / "sources.json")] = (
        json.dumps({"schema_version": 2, "sources": registry_records}, indent=2, sort_keys=True)
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
    for receipt in lineage_migration_receipts:
        destination = _inside(
            vault,
            vault
            / "receipts"
            / "source-lineage"
            / f"migration-{receipt['source_lineage_id']}.json",
        )
        write_plan[destination] = (
            json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        ).encode()
    for receipt in (*generation_receipts, *restoration_receipts):
        receipt_hash = hashlib.sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
        prefix = (
            "generation"
            if receipt["receipt_type"] == "source-lineage-generation-allocation"
            else "restoration"
        )
        destination = _inside(
            vault,
            vault
            / "receipts"
            / "source-lineage"
            / f"{prefix}-{receipt['source_lineage_id']}-{receipt_hash}.json",
        )
        write_plan[destination] = (
            json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        ).encode()
    # AS-INGEST-MANIFEST-001: merge vault-wide discovery snapshot + reports by
    # source_id so narrower batches do not erase sibling-project inventory.
    batch_project_uuids = set(project_identity.values())
    deleted_source_ids = _batch_deleted_source_ids(registry_records, batch_project_uuids)
    prior_manifest = _load_vault_json(vault / "sources" / "manifests" / "source-manifest.json")
    merged_manifest = merge_discovery_manifest(
        prior_manifest if isinstance(prior_manifest, dict) else None,
        manifest,
        deleted_source_ids=deleted_source_ids,
    )
    active_source_ids = {
        str(item["source_id"])
        for item in merged_manifest.get("sources", [])
        if isinstance(item, dict) and item.get("source_id")
    }
    prior_report = _load_vault_json(vault / "generated" / "reports" / "ingestion-report.json")
    merged_report = merge_ingestion_report(
        prior_report if isinstance(prior_report, dict) else None,
        report,
        merged_manifest=merged_manifest,
        deleted_source_ids=deleted_source_ids,
    )
    prior_secrets = _load_vault_json(vault / "generated" / "reports" / "secret-findings.json")
    prior_secret_list = (
        prior_secrets
        if isinstance(prior_secrets, list)
        else (
            prior_secrets.get("findings")
            if isinstance(prior_secrets, dict) and isinstance(prior_secrets.get("findings"), list)
            else None
        )
    )
    merged_secrets = merge_secret_findings(
        [item for item in prior_secret_list if isinstance(item, dict)]
        if isinstance(prior_secret_list, list)
        else None,
        security_findings,
        deleted_source_ids=deleted_source_ids,
        active_source_ids=active_source_ids,
    )
    prior_injection = _load_vault_json(
        vault / "generated" / "reports" / "injection-findings.json"
    )
    merged_injections = merge_injection_findings(
        prior_injection if isinstance(prior_injection, (dict, list)) else None,
        injection_findings,
        deleted_source_ids=deleted_source_ids,
        active_source_ids=active_source_ids,
    )
    write_plan[_inside(vault, vault / "sources" / "manifests" / "source-manifest.json")] = (
        json.dumps(merged_manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
    write_plan[_inside(vault, vault / "generated" / "reports" / "ingestion-report.json")] = (
        json.dumps(merged_report, indent=2, sort_keys=True) + "\n"
    ).encode()
    write_plan[_inside(vault, vault / "generated" / "reports" / "secret-findings.json")] = (
        json.dumps(merged_secrets, indent=2, sort_keys=True) + "\n"
    ).encode()
    write_plan[_inside(vault, vault / "generated" / "reports" / "injection-findings.json")] = (
        json.dumps(
            {"schema_version": 1, "findings": merged_injections},
            indent=2,
            sort_keys=True,
        )
        + "\n"
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
    project_candidates: dict[str, tuple[CompilationCandidate, ...]] = {}
    for project, entries in sorted(projects.items()):
        knowledge = compile_knowledge(
            project,
            entries,
            vault,
            event_entries.get(project, []),
        )
        project_candidates[project] = knowledge.candidates
        for relative_path, expected_bytes in knowledge.preconditions.items():
            marker_preconditions[_inside(vault, vault / relative_path)] = expected_bytes
        for relative, content in render_bundle(knowledge, project).items():
            destination = _inside(vault, vault / relative)
            write_plan[destination] = _generated_content(
                destination, content
            ).encode()
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
    # Derived indexes are part of the same staged transaction.  The overlay
    # lets index generation see canonical state that is not promoted yet.
    from project_atlas.indexes import canonical_index_payloads

    write_plan.update(canonical_index_payloads(vault, write_plan))
    _assert_state_compare_and_swap(marker_preconditions)
    try:
        _promote(write_plan)
    except Exception as exc:
        # §7.8: promotable candidates reach PROMOTION_FAILED; canonical state
        # is untouched (the rollback inside `_promote` stays authoritative).
        _quarantine_promotion_failure(vault, project_candidates, exc)
        raise
    _clear_promotion_failure_report(vault)
    _verify_identity_post_state(
        vault, project_identity, identity_markers, allocated_projects
    )
    return {
        "ok": True,
        "projects": len(projects),
        "documents_ingested": len(imported),
        "events_ingested": len(prepared_events),
        "events_quarantined": len(quarantined_events),
        "security_findings": len(security_findings),
        "inventory_sha256": manifest.get("inventory_sha256"),
    }


def ingest(
    manifest_path: Path,
    vault: Path,
    *,
    uuid_provider: ProjectUuidProvider = production_project_uuid,
) -> dict[str, Any]:
    """Run ingestion under Core-local project identity guards."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = _manifest_records(manifest)
    projects = sorted(
        {
            str(record.likely_project)
            for record in sources
            if record.likely_project and record.likely_project != "unknown-project"
        }
    )
    vault = vault.expanduser().resolve()
    with ExitStack() as stack:
        for project in projects:
            lock_key = hashlib.sha256(project.encode("utf-8")).hexdigest()[:20]
            stack.enter_context(
                ProjectIdentityLock(vault / ".atlas" / "identity-locks" / f"{lock_key}.lock")
            )
        return _ingest(manifest_path, vault, uuid_provider=uuid_provider)
