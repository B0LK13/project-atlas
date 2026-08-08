"""Strict structural and provenance validation for the Core slice."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from project_atlas.domain.authority_semantics import AuthoritativeStateRecord
from project_atlas.domain.temporal import CurrentStateRecord
from project_atlas.portfolio import build_portfolio_payloads
from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.source_identity import canonical_source_sha256

LINK = re.compile(r"\]\(([^)]+)\)")


def validate(vault: Path) -> dict[str, Any]:
    errors: list[str] = []
    for required in ("index.md", "projects/index.md", "sources/index.md", "01-portfolio/index.md"):
        if not (vault / required).is_file():
            errors.append(f"missing required generated file: {required}")
    for markdown in sorted(vault.rglob("*.md")):
        if ".tmp" in markdown.parts:
            continue
        relative = markdown.relative_to(vault)
        if relative.parts[0] == "sources":
            # Layer A imported evidence is raw, immutable source content: its
            # links are relative to the source repository, not the Vault, so
            # link resolution applies to generated layers only (AS-EXT-001A).
            continue
        text = markdown.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://", "#")):
                continue
            candidate = (markdown.parent / target.split("#", 1)[0]).resolve()
            try:
                candidate.relative_to(vault.resolve())
            except ValueError:
                errors.append(f"link escapes vault: {markdown.relative_to(vault)} -> {target}")
            else:
                if not candidate.is_file():
                    errors.append(f"broken link: {markdown.relative_to(vault)} -> {target}")
        if markdown.match("projects/*/concepts.md"):
            _validate_okf_concept_note(vault, markdown, errors)
    _validate_knowledge_state(vault, errors)
    _validate_portfolio(vault, errors)
    return {"ok": not errors, "errors": errors, "markdown_files": len(list(vault.rglob("*.md")))}


def _validate_okf_concept_note(vault: Path, path: Path, errors: list[str]) -> None:
    """Validate OKF frontmatter resources and the concept record contract."""
    relative = path.relative_to(vault)
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append(f"OKF concept note lacks frontmatter: {relative}")
        return
    try:
        _, raw_frontmatter, _ = text.split("---", 2)
        frontmatter = yaml.safe_load(raw_frontmatter)
        if not isinstance(frontmatter, dict):
            raise ValueError("frontmatter must be an object")
        validate_record(frontmatter, "concept-record")
    except (ValueError, yaml.YAMLError, SchemaValidationError) as exc:
        errors.append(f"invalid OKF concept note {relative}: {exc}")
        return
    resource = frontmatter.get("resource")
    if isinstance(resource, str):
        _validate_vault_resource(vault, resource, errors, relative)
    for source in frontmatter.get("sources", []):
        if isinstance(source, dict):
            _validate_vault_resource(vault, str(source.get("resource", "")), errors, relative)


def _validate_vault_resource(
    vault: Path, resource: str, errors: list[str], owner: Path
) -> None:
    candidate = (vault / resource).resolve()
    try:
        candidate.relative_to(vault.resolve())
    except ValueError:
        errors.append(f"OKF resource escapes Vault: {owner} -> {resource}")
    else:
        if not candidate.is_file():
            errors.append(f"OKF resource target missing: {owner} -> {resource}")


def _validate_knowledge_state(vault: Path, errors: list[str]) -> None:
    """Validate AS-CORE-003 machine state and provenance confinement."""
    sources: dict[str, str | None] = {}
    sources_by_lineage: dict[str, str | None] = {}
    source_state = vault / "state" / "sources.json"
    if source_state.is_file():
        try:
            raw = json.loads(source_state.read_text(encoding="utf-8"))
            source_items = [item for item in raw.get("sources", []) if isinstance(item, dict)]
            for item in source_items:
                if item.get("source_lineage_id"):
                    sources_by_lineage[str(item["source_lineage_id"])] = item.get(
                        "current_content_sha256", item.get("sha256")
                    )
                if item.get("source_id"):
                    source_id = str(item["source_id"])
                    if source_id in sources and sources[source_id] != item.get("sha256"):
                        sources[source_id] = None
                    else:
                        sources[source_id] = item.get("sha256")
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError) as exc:
            errors.append(f"invalid source state for knowledge validation: {exc}")
    for path in _json_files(vault, "state", "claims"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for claim in raw.get("claims", []):
                validate_record(claim, "claim")
                for ref in claim.get("provenance", []):
                    _validate_provenance(vault, ref, sources, sources_by_lineage, errors, path)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            SchemaValidationError,
            AttributeError,
            TypeError,
        ) as exc:
            errors.append(f"invalid claim state {path.relative_to(vault)}: {exc}")
    for path in _json_files(vault, "state", "concepts"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for concept in raw.get("concepts", []):
                validate_record(concept, "concept-record")
                for ref in concept.get("sources", []):
                    _validate_provenance(vault, ref, sources, sources_by_lineage, errors, path)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            SchemaValidationError,
            AttributeError,
            TypeError,
        ) as exc:
            errors.append(f"invalid concept state {path.relative_to(vault)}: {exc}")
    for path in _json_files(vault, "state", "authority"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for authority in raw.get("authorities", []):
                validate_record(authority, "authority-record")
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            SchemaValidationError,
            AttributeError,
            TypeError,
        ) as exc:
            errors.append(f"invalid authority state {path.relative_to(vault)}: {exc}")
    for path in _json_files(vault, "review", "conflicts"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for conflict in raw.get("entries", []):
                validate_record(conflict, "conflict-record")
                for ref in conflict.get("provenance", []):
                    _validate_provenance(vault, ref, sources, sources_by_lineage, errors, path)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            SchemaValidationError,
            AttributeError,
            TypeError,
        ) as exc:
            errors.append(f"invalid conflict state {path.relative_to(vault)}: {exc}")
    for path in _json_files(vault, "review", "pending"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for review in raw.get("entries", []):
                validate_record(review, "review-entry")
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            SchemaValidationError,
            AttributeError,
            TypeError,
        ) as exc:
            errors.append(f"invalid review state {path.relative_to(vault)}: {exc}")
    for path in _json_files(vault, "state", "claim-lifecycle"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for lifecycle in raw.get("claims", []):
                validate_record(lifecycle, "claim-lifecycle")
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            SchemaValidationError,
            AttributeError,
            TypeError,
        ) as exc:
            errors.append(f"invalid lifecycle state {path.relative_to(vault)}: {exc}")
    # AS-CORE-007-FR-011: additive checks when 005/006 state files exist.
    # Missing files on legacy vaults are not errors.
    _validate_current_and_authoritative_state(vault, errors)
    _validate_indexes(vault, errors)
    _validate_injection_findings(vault, errors)


def _validate_current_and_authoritative_state(vault: Path, errors: list[str]) -> None:
    """AS-CORE-007-FR-011: validate 005/006 state files when present (additive)."""
    for path in _json_files(vault, "state", "current-state"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                errors.append(f"invalid current-state root {path.relative_to(vault)}")
                continue
            for item in raw.get("current_states", []):
                CurrentStateRecord.model_validate(item)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            AttributeError,
            TypeError,
            ValueError,
        ) as exc:
            errors.append(f"invalid current-state {path.relative_to(vault)}: {exc}")
    for path in _json_files(vault, "state", "authoritative-state"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                errors.append(f"invalid authoritative-state root {path.relative_to(vault)}")
                continue
            for item in raw.get("authoritative_states", []):
                AuthoritativeStateRecord.model_validate(item)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            AttributeError,
            TypeError,
            ValueError,
        ) as exc:
            errors.append(f"invalid authoritative-state {path.relative_to(vault)}: {exc}")


def _validate_injection_findings(vault: Path, errors: list[str]) -> None:
    """Check AS-SEC-001 quarantine report integrity."""
    path = vault / "generated" / "reports" / "injection-findings.json"
    if not path.is_file():
        return
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ValueError("invalid injection-findings schema_version")
        findings = raw.get("findings")
        if not isinstance(findings, list):
            raise ValueError("findings must be a list")
        quarantined_ids: set[str] = set()
        for finding in findings:
            if not isinstance(finding, dict):
                raise ValueError("finding must be an object")
            for key in ("source_id", "path", "rule", "confidence", "disposition"):
                if key not in finding:
                    raise ValueError(f"missing injection finding field: {key}")
            if finding["disposition"] != "quarantined":
                raise ValueError(
                    f"injection finding disposition must be 'quarantined': {finding['source_id']}"
                )
            if "text" in finding:
                raise ValueError(
                    f"injection finding must not carry matched text: {finding['source_id']}"
                )
            quarantined_ids.add(str(finding["source_id"]))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"invalid injection findings report: {exc}")
        return
    # Verify no quarantined source was projected into trusted Layer B/C state.
    for path in _json_files(vault, "state", "claims"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for claim in raw.get("claims", []):
            for ref in claim.get("provenance", []):
                if str(ref.get("source_id", "")) in quarantined_ids:
                    errors.append(
                        f"quarantined source {ref.get('source_id')} appears in claims: "
                        f"{path.relative_to(vault)}"
                    )
    for path in _json_files(vault, "state", "concepts"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for concept in raw.get("concepts", []):
            for ref in concept.get("sources", []):
                if str(ref.get("source_id", "")) in quarantined_ids:
                    errors.append(
                        f"quarantined source {ref.get('source_id')} appears in concepts: "
                        f"{path.relative_to(vault)}"
                    )


def _validate_portfolio(vault: Path, errors: list[str]) -> None:
    """Reject drift between generated/portfolio/*.json and canonical state
    (AS-MVP-001), mirroring the build-indexes drift-rejection convention."""
    portfolio_root = vault / "generated" / "portfolio"
    if not portfolio_root.is_dir():
        return
    stale_path = portfolio_root / "stale-knowledge.json"
    reference_date = datetime.now(UTC)
    if stale_path.is_file():
        try:
            raw = json.loads(stale_path.read_text(encoding="utf-8"))
            candidate = raw.get("reference_date")
            if isinstance(candidate, str):
                reference_date = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            errors.append(
                "invalid generated/portfolio/stale-knowledge.json: unparsable reference_date"
            )
            return
    try:
        expected = build_portfolio_payloads(vault, reference_date=reference_date)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"unable to recompute portfolio for drift check: {exc}")
        return
    quarantined_ids = set()
    injection_path = vault / "generated" / "reports" / "injection-findings.json"
    if injection_path.is_file():
        raw = _json_or_default(injection_path)
        quarantined_ids = {
            str(finding.get("source_id"))
            for finding in raw.get("findings", [])
            if isinstance(finding, dict)
        }
    for name, expected_payload in sorted(expected.items()):
        path = portfolio_root / name
        if not path.is_file():
            errors.append(f"missing generated portfolio output: generated/portfolio/{name}")
            continue
        try:
            actual_payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid generated portfolio output generated/portfolio/{name}: {exc}")
            continue
        if actual_payload != expected_payload:
            errors.append(f"portfolio drift detected: generated/portfolio/{name}")
        _validate_no_quarantined_leakage(name, actual_payload, quarantined_ids, errors)


def _validate_no_quarantined_leakage(
    name: str, payload: Any, quarantined_ids: set[str], errors: list[str]
) -> None:
    """AS-SEC-001 boundary: no quarantined source_id may appear as a cited
    provenance reference inside any portfolio output (safe aggregate counts
    are permitted; individual references to quarantined sources are not)."""
    if not quarantined_ids:
        return
    serialized = json.dumps(payload)
    for source_id in quarantined_ids:
        if f'"{source_id}"' in serialized:
            errors.append(
                f"quarantined source {source_id} referenced in generated/portfolio/{name}"
            )


def _json_or_default(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _json_files(vault: Path, *parts: str) -> list[Path]:
    directory = vault.joinpath(*parts)
    return sorted(directory.glob("*.json")) if directory.is_dir() else []


def _validate_indexes(vault: Path, errors: list[str]) -> None:
    """Check generated lexical indexes against canonical machine state."""
    legacy_root = vault / "indexes"
    if legacy_root.exists():
        errors.append(
            "obsolete generated index directory: indexes; remove it and rebuild "
            "under generated/indexes"
        )
    index_root = vault / "generated" / "indexes"
    if not index_root.is_dir():
        return
    state_ids: dict[str, set[str]] = {
        "claims": set(),
        "concepts": set(),
        "conflicts": set(),
        "authority": set(),
        "sources": set(),
    }
    for path in _json_files(vault, "state", "claims"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        state_ids["claims"].update(
            str(item["claim_id"])
            for item in raw.get("claims", [])
            if isinstance(item, dict) and item.get("claim_id")
        )
    for path in _json_files(vault, "state", "concepts"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        state_ids["concepts"].update(
            str(item["concept_id"])
            for item in raw.get("concepts", [])
            if isinstance(item, dict) and item.get("concept_id")
        )
    for path in _json_files(vault, "review", "conflicts"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        state_ids["conflicts"].update(
            str(item["conflict_id"])
            for item in raw.get("entries", [])
            if isinstance(item, dict) and item.get("conflict_id")
        )
    for path in _json_files(vault, "state", "authority"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        state_ids["authority"].update(
            str(item["authority_id"])
            for item in raw.get("authorities", [])
            if isinstance(item, dict) and item.get("authority_id")
        )
    source_path = vault / "state" / "sources.json"
    if source_path.is_file():
        raw = json.loads(source_path.read_text(encoding="utf-8"))
        state_ids["sources"].update(
            str(item["source_lineage_id"])
            for item in raw.get("sources", [])
            if isinstance(item, dict) and item.get("source_lineage_id")
        )
    for kind in ("claims", "concepts", "conflicts", "authority", "sources"):
        path = index_root / f"{kind}.json"
        if not path.is_file():
            errors.append(f"missing generated lexical index: generated/indexes/{kind}.json")
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            indexed = raw.get("ids", [])
            if sorted(indexed) != sorted(state_ids[kind]):
                errors.append(f"index/state mismatch: generated/indexes/{kind}.json")
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError) as exc:
            errors.append(f"invalid generated lexical index generated/indexes/{kind}.json: {exc}")
    provenance_path = index_root / "provenance.json"
    if not provenance_path.is_file():
        errors.append("missing generated lexical index: generated/indexes/provenance.json")
    else:
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            for key in ("by_source_lineage_id", "by_receipt_id"):
                if not isinstance(provenance.get(key), dict):
                    errors.append(
                        "invalid generated lexical index "
                        f"generated/indexes/provenance.json: {key}"
                    )
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError) as exc:
            errors.append(
                "invalid generated lexical index "
                f"generated/indexes/provenance.json: {exc}"
            )


def _validate_provenance(
    vault: Path,
    reference: dict[str, Any],
    sources: dict[str, str | None],
    sources_by_lineage: dict[str, str | None],
    errors: list[str],
    owner: Path,
) -> None:
    resource = str(reference.get("resource", ""))
    candidate = (vault / resource).resolve()
    try:
        candidate.relative_to(vault.resolve())
    except ValueError:
        errors.append(f"provenance escapes Vault: {owner.relative_to(vault)} -> {resource}")
        return
    if not candidate.is_file():
        errors.append(f"provenance target missing: {owner.relative_to(vault)} -> {resource}")
        return
    source_id = str(reference.get("source_id", ""))
    source_lineage_id = reference.get("source_lineage_id")
    expected = (
        sources_by_lineage.get(str(source_lineage_id))
        if source_lineage_id
        else sources.get(source_id)
    )
    actual = _sha256(candidate)
    if expected and actual != expected:
        errors.append(f"provenance hash mismatch: {owner.relative_to(vault)} -> {source_id}")
    supplied = reference.get("sha256")
    # Agent-event provenance uses the package aggregate hash, while the
    # resource is the human-readable event projection. Package integrity is
    # verified at ingestion; it is not the byte hash of this projection.
    if supplied and not reference.get("receipt_id") and actual != supplied:
        errors.append(f"claim hash mismatch: {owner.relative_to(vault)} -> {source_id}")


def _sha256(path: Path) -> str:
    """Return the same canonical source hash used during discovery."""
    return canonical_source_sha256(path)
