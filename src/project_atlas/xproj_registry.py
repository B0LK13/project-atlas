"""AS-XPROJ-001 — Global / shared entity identity registry.

Explicit registration only. Join keys map
``(project_id, project_local_entity_id) → global_entity_id`` via registration
records — never via display name / slug / fuzzy / LLM.

Never writes claims, temporal/authoritative state, knowledge-query caches,
Control Plane ``relationships/``, or Graph Layer paths. Never elevates above
``authority.level = derived``.

Truth boundary: CROSS-PROJECT IDENTITY ≠ AUTOMATIC AUTHORITY
(AS-XPROJ-INV-TRUTH-001). Name/string ≠ identity (AS-XPROJ-INV-NO-FUZZY-001).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from project_atlas.schema import validate_record

PACKAGE_ID = "AS-XPROJ-001"
AUTHORITY_LEVEL = "derived"
TRUTH_BOUNDARY = "CROSS-PROJECT IDENTITY ≠ AUTOMATIC AUTHORITY"

MVP_ENTITY_CLASSES: frozenset[str] = frozenset(
    {
        "technology",
        "service",
        "library",
        "infrastructure",
        "environment",
        "external-api",
        "organization",
        "extension",
    }
)

PHYSICAL_RESOURCE_MARKERS: frozenset[str] = frozenset(
    {
        "host",
        "hostname",
        "arn",
        "instance-id",
        "disk",
        "nic",
        "volume",
        "ip-address",
        "mac-address",
    }
)

ALLOWED_WRITE_PREFIXES: tuple[str, ...] = (
    "state/global-entities/",
)

_FORBIDDEN_WRITE_PREFIXES: tuple[str, ...] = (
    "relationships/",
    "state/current-state/",
    "state/authoritative-state/",
    "claims/",
    "generated/indexes/",
    "generated/query/",
    "generated/graph/",
    "generated/xproj/edges/",
    "generated/xproj/duplicate-candidates/",
    "generated/xproj/conflicts/",
    "generated/xproj/indexes/",
)

_GLOBAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

EntityClass = Literal[
    "technology",
    "service",
    "library",
    "infrastructure",
    "environment",
    "external-api",
    "organization",
    "extension",
]

QuarantineCategory = Literal[
    "ambiguous-join",
    "colliding-registration",
    "class-conflict",
    "name-only-merge-forbidden",
    "fuzzy-identity-forbidden",
    "physical-resource-promotion-forbidden",
    "unknown-class",
    "missing-registration",
]

JoinStatus = Literal["joined", "quarantine_candidate"]


class XprojRegistryError(ValueError):
    """Fail-closed XPROJ registry error (metadata-only message)."""


@dataclass(frozen=True)
class EvidenceRef:
    relative_path: str
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {"relative_path": self.relative_path, "sha256": self.sha256}


@dataclass(frozen=True)
class GlobalEntityRecord:
    """Explicit global entity registration (promoted registry record)."""

    global_entity_id: str
    entity_class: EntityClass
    display_name: str
    notes: str | None = None
    attributes: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "global_entity_id": self.global_entity_id,
            "entity_class": self.entity_class,
            "display_name": self.display_name,
            "authority": {
                "level": AUTHORITY_LEVEL,
                "note": (
                    "XPROJ registry is derived portfolio intelligence; "
                    "not claim/temporal/authoritative truth."
                ),
            },
            "registration_kind": "explicit",
            "status": "registered",
            "truth_boundary": TRUTH_BOUNDARY,
        }
        if self.notes is not None:
            payload["notes"] = self.notes
        if self.attributes is not None:
            payload["attributes"] = dict(self.attributes)
        return payload

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class JoinKeyRecord:
    """Explicit join key (additive; evidence remains project-scoped)."""

    project_id: str
    project_local_entity_id: str
    global_entity_id: str
    evidence_refs: tuple[EvidenceRef, ...]
    status: JoinStatus = "joined"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "project_id": self.project_id,
            "project_local_entity_id": self.project_local_entity_id,
            "global_entity_id": self.global_entity_id,
            "evidence_refs": [ref.as_dict() for ref in self.evidence_refs],
            "authority": {
                "level": AUTHORITY_LEVEL,
                "note": "Join is additive; evidence remains project-scoped.",
            },
            "status": self.status,
            "truth_boundary": TRUTH_BOUNDARY,
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class QuarantineCandidate:
    """Fail-closed quarantine — never includes winning_choice."""

    candidate_id: str
    category: QuarantineCategory
    reason: str
    inputs_considered: Mapping[str, Any]
    project_id: str | None = None
    project_local_entity_id: str | None = None
    global_entity_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "candidate_id": self.candidate_id,
            "category": self.category,
            "authority": {
                "level": AUTHORITY_LEVEL,
                "note": "Quarantine candidate is derived-only; never pick a winner.",
            },
            "status": "quarantine_candidate",
            "reason": self.reason,
            "inputs_considered": dict(self.inputs_considered),
            "truth_boundary": TRUTH_BOUNDARY,
        }
        if self.project_id is not None:
            payload["project_id"] = self.project_id
        if self.project_local_entity_id is not None:
            payload["project_local_entity_id"] = self.project_local_entity_id
        if self.global_entity_id is not None:
            payload["global_entity_id"] = self.global_entity_id
        return payload

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


@dataclass
class RegistryResult:
    """In-memory registration / join outcome (deterministic ordering on emit)."""

    entities: list[GlobalEntityRecord] = field(default_factory=list)
    joins: list[JoinKeyRecord] = field(default_factory=list)
    quarantine: list[QuarantineCandidate] = field(default_factory=list)

    @property
    def registered_count(self) -> int:
        return len(self.entities)

    @property
    def joined_count(self) -> int:
        return sum(1 for item in self.joins if item.status == "joined")

    @property
    def quarantined_count(self) -> int:
        return len(self.quarantine)


def _redact_reason(reason: str) -> str:
    text = reason.strip()
    lowered = text.lower()
    for needle in ("password=", "secret=", "token=", "api_key=", "bearer "):
        if needle in lowered:
            return "redacted-sensitive-reason"
    return text[:240]


def _safe_name(token: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", token).strip("-")
    return cleaned or "entity"


def _normalize_class(raw: str | None) -> EntityClass | None:
    if raw is None:
        return None
    token = raw.strip().casefold().replace("_", "-")
    aliases = {
        "externalapi": "external-api",
        "external-api": "external-api",
        "ext-api": "external-api",
        "org": "organization",
    }
    token = aliases.get(token, token)
    if token in MVP_ENTITY_CLASSES:
        return token  # type: ignore[return-value]
    return None


def _is_physical_promotion(
    *,
    entity_class: EntityClass,
    display_name: str,
    attributes: Mapping[str, Any] | None,
) -> bool:
    if entity_class not in {"technology", "service"}:
        return False
    markers: list[str] = []
    if attributes:
        for key, value in attributes.items():
            markers.append(str(key).casefold())
            if isinstance(value, str):
                markers.append(value.casefold())
    markers.append(display_name.casefold())
    joined = " ".join(markers)
    for marker in PHYSICAL_RESOURCE_MARKERS:
        if marker in joined:
            return True
    # ARN / hostname-ish patterns without inventing fuzzy identity.
    if re.search(r"\barn:[a-z0-9-]+:", joined):
        return True
    return bool(re.search(r"\b(?:ip|mac)[-_ ]?address\b", joined))


def _validate_global_id(global_entity_id: str) -> str:
    token = global_entity_id.strip()
    if not token or not _GLOBAL_ID_RE.fullmatch(token):
        raise XprojRegistryError("global-entity-id-invalid")
    return token


def _validate_evidence(refs: Sequence[EvidenceRef | Mapping[str, str]]) -> tuple[EvidenceRef, ...]:
    out: list[EvidenceRef] = []
    for item in refs:
        if isinstance(item, EvidenceRef):
            ref = item
        else:
            relative = str(item.get("relative_path") or "").strip()
            digest = str(item.get("sha256") or "").strip()
            if not relative or not _SHA256_RE.fullmatch(digest):
                raise XprojRegistryError("evidence-ref-invalid")
            if (
                relative.startswith(("/", "\\"))
                or "\\" in relative
                or ".." in Path(relative).parts
            ):
                raise XprojRegistryError(f"path-escape:{relative}")
            ref = EvidenceRef(relative_path=relative, sha256=digest)
        out.append(ref)
    if not out:
        raise XprojRegistryError("evidence-refs-required")
    out.sort(key=lambda item: (item.relative_path.casefold(), item.sha256))
    return tuple(out)


def register_global_entity(
    *,
    global_entity_id: str | None,
    entity_class: str | None,
    display_name: str | None,
    notes: str | None = None,
    attributes: Mapping[str, Any] | None = None,
    mint_from_name: bool = False,
    fuzzy: bool = False,
) -> GlobalEntityRecord | QuarantineCandidate:
    """Explicit registration. Name-only / fuzzy mint attempts fail closed."""
    if fuzzy:
        return QuarantineCandidate(
            candidate_id=f"q-fuzzy-{_safe_name(display_name or 'unknown')}",
            category="fuzzy-identity-forbidden",
            reason="fuzzy-identity-forbidden",
            inputs_considered={"display_name": display_name or ""},
        )
    if mint_from_name or global_entity_id is None or not str(global_entity_id).strip():
        return QuarantineCandidate(
            candidate_id=f"q-name-only-{_safe_name(display_name or 'unknown')}",
            category="name-only-merge-forbidden",
            reason="name-only-merge-forbidden",
            inputs_considered={"display_name": display_name or ""},
        )

    label = (display_name or "").strip()
    if not label:
        raise XprojRegistryError("display-name-required")

    normalized = _normalize_class(entity_class)
    if normalized is None:
        return QuarantineCandidate(
            candidate_id=f"q-class-{_safe_name(str(entity_class) or 'unknown')}",
            category="unknown-class",
            reason="unknown-class",
            inputs_considered={
                "entity_class": entity_class or "",
                "display_name": label,
            },
            global_entity_id=str(global_entity_id).strip(),
        )

    if _is_physical_promotion(
        entity_class=normalized,
        display_name=label,
        attributes=attributes,
    ):
        return QuarantineCandidate(
            candidate_id=f"q-physical-{_safe_name(str(global_entity_id))}",
            category="physical-resource-promotion-forbidden",
            reason="physical-resource-promotion-forbidden",
            inputs_considered={
                "entity_class": normalized,
                "display_name": label,
            },
            global_entity_id=str(global_entity_id).strip(),
        )

    gid = _validate_global_id(str(global_entity_id))
    # Display name alone must never equal the global id mint path.
    if gid.casefold() == label.casefold() or gid.casefold() == _safe_name(label).casefold():
        return QuarantineCandidate(
            candidate_id=f"q-name-collapse-{_safe_name(gid)}",
            category="name-only-merge-forbidden",
            reason="global-id-equals-display-name",
            inputs_considered={"display_name": label, "global_entity_id": gid},
            global_entity_id=gid,
        )

    record = GlobalEntityRecord(
        global_entity_id=gid,
        entity_class=normalized,
        display_name=label,
        notes=_redact_reason(notes) if notes else None,
        attributes=dict(attributes) if attributes else None,
    )
    validate_record(record.as_dict(), "xproj-global-entity")
    return record


def register_join(
    *,
    project_id: str,
    project_local_entity_id: str,
    global_entity_id: str,
    evidence_refs: Sequence[EvidenceRef | Mapping[str, str]],
    registry: Mapping[str, GlobalEntityRecord] | Sequence[GlobalEntityRecord],
    existing_joins: Sequence[JoinKeyRecord] = (),
) -> JoinKeyRecord | QuarantineCandidate:
    """Additive explicit join. Ambiguous multi-join → quarantine (no winner)."""
    pid = project_id.strip()
    local = project_local_entity_id.strip()
    if not pid or not local:
        raise XprojRegistryError("join-keys-required")
    if "/" in pid or "\\" in pid or pid in {".", ".."}:
        raise XprojRegistryError("project-id-unsafe")

    gid = _validate_global_id(global_entity_id)
    refs = _validate_evidence(evidence_refs)

    entities: dict[str, GlobalEntityRecord]
    if isinstance(registry, Mapping):
        entities = dict(registry)
    else:
        entities = {item.global_entity_id: item for item in registry}

    if gid not in entities:
        return QuarantineCandidate(
            candidate_id=f"q-missing-{_safe_name(gid)}-{_safe_name(local)}",
            category="missing-registration",
            reason="missing-registration",
            inputs_considered={
                "project_id": pid,
                "project_local_entity_id": local,
                "global_entity_id": gid,
            },
            project_id=pid,
            project_local_entity_id=local,
            global_entity_id=gid,
        )

    prior = [
        join
        for join in existing_joins
        if join.status == "joined"
        and join.project_id == pid
        and join.project_local_entity_id == local
    ]
    distinct_globals = {join.global_entity_id for join in prior}
    if distinct_globals and gid not in distinct_globals:
        return QuarantineCandidate(
            candidate_id=f"q-ambiguous-{_safe_name(pid)}-{_safe_name(local)}",
            category="ambiguous-join",
            reason="ambiguous-join",
            inputs_considered={
                "project_id": pid,
                "project_local_entity_id": local,
                "existing_global_entity_ids": sorted(distinct_globals),
                "requested_global_entity_id": gid,
            },
            project_id=pid,
            project_local_entity_id=local,
            global_entity_id=gid,
        )

    # Class-conflict: same display string joined as different classes across projects
    # is allowed as distinct globals; colliding re-registration of one local to two
    # classes via same global id is refused above. Detect re-use of one global id
    # with a conflicting class claim on the registration map (caller supplies).
    record = JoinKeyRecord(
        project_id=pid,
        project_local_entity_id=local,
        global_entity_id=gid,
        evidence_refs=refs,
        status="joined",
    )
    validate_record(record.as_dict(), "xproj-join-key")
    return record


def detect_class_collapse(
    *,
    display_name: str,
    entities: Sequence[GlobalEntityRecord],
) -> QuarantineCandidate | None:
    """Same display name + different classes must not share a global_entity_id."""
    label = display_name.strip().casefold()
    matching = [item for item in entities if item.display_name.casefold() == label]
    by_id: dict[str, set[str]] = {}
    for item in matching:
        by_id.setdefault(item.global_entity_id, set()).add(item.entity_class)
    for gid, classes in sorted(by_id.items()):
        if len(classes) > 1:
            return QuarantineCandidate(
                candidate_id=f"q-class-conflict-{_safe_name(gid)}",
                category="class-conflict",
                reason="class-collapse-forbidden",
                inputs_considered={
                    "display_name": display_name,
                    "global_entity_id": gid,
                    "entity_classes": sorted(classes),
                },
                global_entity_id=gid,
            )
    return None


def apply_registrations(
    requests: Sequence[Mapping[str, Any]],
) -> RegistryResult:
    """Deterministic batch apply for entities then joins (stable sort)."""
    result = RegistryResult()
    entity_map: dict[str, GlobalEntityRecord] = {}

    entity_reqs = [item for item in requests if item.get("kind") == "entity"]
    join_reqs = [item for item in requests if item.get("kind") == "join"]
    entity_reqs.sort(
        key=lambda item: (
            str(item.get("global_entity_id") or "").casefold(),
            str(item.get("entity_class") or "").casefold(),
            str(item.get("display_name") or "").casefold(),
        )
    )
    join_reqs.sort(
        key=lambda item: (
            str(item.get("project_id") or "").casefold(),
            str(item.get("project_local_entity_id") or "").casefold(),
            str(item.get("global_entity_id") or "").casefold(),
        )
    )

    for req in entity_reqs:
        raw_attrs = req.get("attributes")
        attributes: Mapping[str, Any] | None = (
            raw_attrs if isinstance(raw_attrs, Mapping) else None
        )
        entity_outcome = register_global_entity(
            global_entity_id=(
                str(req["global_entity_id"]) if req.get("global_entity_id") is not None else None
            ),
            entity_class=str(req["entity_class"]) if req.get("entity_class") is not None else None,
            display_name=str(req["display_name"]) if req.get("display_name") is not None else None,
            notes=str(req["notes"]) if req.get("notes") is not None else None,
            attributes=attributes,
            mint_from_name=bool(req.get("mint_from_name")),
            fuzzy=bool(req.get("fuzzy")),
        )
        if isinstance(entity_outcome, QuarantineCandidate):
            result.quarantine.append(entity_outcome)
            continue
        if entity_outcome.global_entity_id in entity_map:
            prior = entity_map[entity_outcome.global_entity_id]
            if prior.entity_class != entity_outcome.entity_class:
                result.quarantine.append(
                    QuarantineCandidate(
                        candidate_id=f"q-collide-{_safe_name(entity_outcome.global_entity_id)}",
                        category="colliding-registration",
                        reason="colliding-registration",
                        inputs_considered={
                            "global_entity_id": entity_outcome.global_entity_id,
                            "prior_class": prior.entity_class,
                            "new_class": entity_outcome.entity_class,
                        },
                        global_entity_id=entity_outcome.global_entity_id,
                    )
                )
                continue
            # Idempotent same registration — keep first.
            continue
        entity_map[entity_outcome.global_entity_id] = entity_outcome
        result.entities.append(entity_outcome)

    # Per distinct display name: same global_entity_id must not span classes.
    names = sorted({item.display_name for item in result.entities}, key=str.casefold)
    for name in names:
        hit = detect_class_collapse(display_name=name, entities=result.entities)
        if hit is not None:
            result.quarantine.append(hit)

    joins: list[JoinKeyRecord] = []
    for req in join_reqs:
        raw_refs = req.get("evidence_refs") or []
        evidence: list[EvidenceRef | Mapping[str, str]] = []
        if isinstance(raw_refs, Sequence) and not isinstance(raw_refs, (str, bytes)):
            for item in raw_refs:
                if isinstance(item, EvidenceRef):
                    evidence.append(item)
                elif isinstance(item, Mapping):
                    evidence.append(item)  # validated inside register_join
        join_outcome = register_join(
            project_id=str(req.get("project_id") or ""),
            project_local_entity_id=str(req.get("project_local_entity_id") or ""),
            global_entity_id=str(req.get("global_entity_id") or ""),
            evidence_refs=evidence,
            registry=entity_map,
            existing_joins=joins,
        )
        if isinstance(join_outcome, QuarantineCandidate):
            result.quarantine.append(join_outcome)
            continue
        joins.append(join_outcome)
        result.joins.append(join_outcome)

    result.entities.sort(key=lambda item: item.global_entity_id.casefold())
    result.joins.sort(
        key=lambda item: (
            item.project_id.casefold(),
            item.project_local_entity_id.casefold(),
            item.global_entity_id.casefold(),
        )
    )
    result.quarantine.sort(key=lambda item: item.candidate_id.casefold())
    return result


def inspect_registry(result: RegistryResult) -> dict[str, Any]:
    """Observability summary — counts only; no secret payloads."""
    return {
        "package_id": PACKAGE_ID,
        "authority_level": AUTHORITY_LEVEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "registered": result.registered_count,
        "joined": result.joined_count,
        "quarantined": result.quarantined_count,
    }


def _safe_vault_relative(vault: Path, relative: str) -> Path:
    if relative.startswith(("/", "\\")) or "\\" in relative or ".." in Path(relative).parts:
        raise XprojRegistryError(f"path-escape:{relative}")
    if not any(relative.startswith(prefix) for prefix in ALLOWED_WRITE_PREFIXES):
        raise XprojRegistryError(f"forbidden-write-prefix:{relative}")
    if any(relative.startswith(prefix) for prefix in _FORBIDDEN_WRITE_PREFIXES):
        raise XprojRegistryError(f"forbidden-write-prefix:{relative}")
    # Nested allowed prefixes under state/global-entities/ only.
    root = vault.expanduser().resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise XprojRegistryError(f"path-escape:{relative}")
    return candidate


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def write_registry_outputs(
    result: RegistryResult,
    *,
    vault: Path,
) -> list[str]:
    """Optional deterministic vault emits under ``state/global-entities/`` only."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise XprojRegistryError(f"vault-missing:{vault}")

    written: list[str] = []
    for record in result.entities:
        safe = _safe_name(record.global_entity_id)
        relative = f"state/global-entities/{safe}.json"
        path = _safe_vault_relative(vault, relative)
        validate_record(record.as_dict(), "xproj-global-entity")
        _write_atomic(path, record.to_json())
        written.append(relative)

    for join in result.joins:
        safe = _safe_name(
            f"{join.project_id}--{join.project_local_entity_id}--{join.global_entity_id}"
        )
        relative = f"state/global-entities/joins/{safe}.json"
        path = _safe_vault_relative(vault, relative)
        validate_record(join.as_dict(), "xproj-join-key")
        _write_atomic(path, join.to_json())
        written.append(relative)

    for candidate in result.quarantine:
        safe = _safe_name(candidate.candidate_id)
        relative = f"state/global-entities/quarantine-candidates/{safe}.json"
        path = _safe_vault_relative(vault, relative)
        validate_record(candidate.as_dict(), "xproj-quarantine-candidate")
        _write_atomic(path, candidate.to_json())
        written.append(relative)

    written.sort()
    return written


def promote_registry_path_forbidden(relative: str) -> None:
    """Public helper for tests: assert a relative path is rejected by path policy."""
    _safe_vault_relative(Path("."), relative)


__all__ = [
    "ALLOWED_WRITE_PREFIXES",
    "AUTHORITY_LEVEL",
    "MVP_ENTITY_CLASSES",
    "PACKAGE_ID",
    "TRUTH_BOUNDARY",
    "EvidenceRef",
    "GlobalEntityRecord",
    "JoinKeyRecord",
    "QuarantineCandidate",
    "RegistryResult",
    "XprojRegistryError",
    "apply_registrations",
    "detect_class_collapse",
    "inspect_registry",
    "promote_registry_path_forbidden",
    "register_global_entity",
    "register_join",
    "write_registry_outputs",
]
