"""AS-CODER-ALPHA-FRESH-AGENT-CHALLENGE-V2 — machine-scored fresh-agent harness.

Question: can a fresh agent receive Atlas Context and understand a project
without re-explanation?

Deterministic core scoring needs no live LLM and no network. Expected answers
are derived from canonical fixture evidence in a *separate* catalog — never
embedded in the generated context pack.

Honesty stamps:
- DEMO_FIXTURE != AUTHENTIC_PILOT
- MODEL_OUTPUT != AUTHORITY
- UNKNOWN stays UNKNOWN when evidence is absent
- superseded decisions are not governing
- hidden benchmark answers inside generated context are forbidden
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from atlas_contracts.identity import safe_relative_component

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-FRESH-AGENT-CHALLENGE-V2"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-fresh-agent-challenge-v2"
SCHEMA_NAME: Final[str] = "atlas.coder-alpha.fresh-agent-challenge.v1"
RECEIPT_DIR: Final[Path] = Path("generated") / "ops" / "fresh-agent"
TRUTH_BOUNDARY: Final[str] = (
    "FRESH-AGENT HARNESS != AUTHENTIC_PILOT / MODEL_OUTPUT != AUTHORITY / "
    "DEMO_FIXTURE != AUTHENTIC_PILOT / UNKNOWN != HEALTHY"
)

REQUIRED_SLOTS: Final[tuple[str, ...]] = (
    "identity",
    "current_state",
    "what_changed",
    "governing_decisions",
    "unknown_conflict",
    "attention",
    "source_health",
    "what_next",
    "supporting_evidence",
)

SlotStatus = Literal["known", "UNKNOWN", "conflict"]
EstateKind = Literal["DEMO_FIXTURE", "SELF_DOGFOOD_DEMO"]

_HIDDEN_PACK_KEYS: Final[frozenset[str]] = frozenset(
    {
        "expected",
        "expected_answers",
        "answer_key",
        "benchmark",
        "gold",
        "gold_answers",
        "hidden_holdout",
        "scoring_rubric",
        "required_tokens",
        "forbidden_tokens",
        "leak_tokens",
    }
)
_MARKDOWN_SUFFIXES: Final[frozenset[str]] = frozenset({".md", ".markdown"})
_ADR_NAME_RE = re.compile(r"\bADR[- ]?(\d+)\b", re.IGNORECASE)
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
_PG_RE = re.compile(r"PostgreSQL\s+(\d+)", re.IGNORECASE)
_STATUS_RE = re.compile(
    r"(?im)^(?:#{1,3}\s*)?status\s*:?\s*(.+)$"
)
_TIMESTAMP_RE = re.compile(r"(?im)^timestamp:\s*(\d{4}-\d{2}-\d{2})\s*$")
_YAML_ID_RE = re.compile(r"(?m)^\s+id:\s*([A-Za-z0-9][A-Za-z0-9._-]{0,63})\s*$")
_YAML_NAME_RE = re.compile(r"(?m)^\s+name:\s*(.+?)\s*$")


class FreshAgentChallengeError(ValueError):
    """Fail-closed fresh-agent harness error."""


@dataclass(frozen=True, slots=True)
class SlotExpectation:
    """Scoring rubric for one question slot. Never written into a context pack."""

    slot: str
    required_tokens: tuple[str, ...] = ()
    forbidden_tokens: tuple[str, ...] = ()
    leak_tokens: tuple[str, ...] = ()
    unknown_required: bool = False
    evidence_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExpectedCatalog:
    """Canonical expected answers derived from fixture evidence, not model preference."""

    project_id: str
    estate_kind: EstateKind
    slots: tuple[SlotExpectation, ...]
    authenticity: dict[str, bool] = field(
        default_factory=lambda: {
            "authentic_pilot": False,
            "demo_fixture_ne_authentic_pilot": True,
        }
    )

    def by_slot(self) -> dict[str, SlotExpectation]:
        return {item.slot: item for item in self.slots}


@dataclass(frozen=True, slots=True)
class ExtractedAnswer:
    slot: str
    status: SlotStatus
    text: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SlotScore:
    slot: str
    covered: bool
    accurate: bool
    stale: bool
    unknown_honest: bool | None
    leak_hits: tuple[str, ...]
    notes: str


@dataclass(frozen=True, slots=True)
class ChallengeScore:
    project_id: str
    estate_kind: EstateKind
    context_coverage: float
    context_accuracy: float
    stale_context_rate: float
    unknown_honesty: float
    cross_project_leak_count: int
    reexplanation_required: bool
    slot_scores: tuple[SlotScore, ...]
    hidden_benchmark_in_pack: bool
    network_required: bool
    honesty: dict[str, object]


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise FreshAgentChallengeError(str(exc)) from exc


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def _contains(haystack: str, needle: str) -> bool:
    return _norm(needle) in _norm(haystack)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _iter_markdown(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _MARKDOWN_SUFFIXES:
            continue
        if any(part.startswith(".") and part not in {".atlas-project.yaml"} for part in path.parts):
            continue
        files.append(path)
    return files


def _project_id_from_marker(project_root: Path) -> str | None:
    marker = project_root / ".atlas-project.yaml"
    if not marker.is_file():
        return None
    match = _YAML_ID_RE.search(_read_text(marker))
    return match.group(1) if match else None


def _project_name_from_marker(project_root: Path) -> str | None:
    marker = project_root / ".atlas-project.yaml"
    if not marker.is_file():
        return None
    match = _YAML_NAME_RE.search(_read_text(marker))
    if not match:
        return None
    return match.group(1).strip().strip("\"'")


def _decision_status(text: str) -> str:
    lowered = _norm(text)
    if "superseded" in lowered:
        return "SUPERSEDED"
    if "rejected" in lowered:
        return "REJECTED"
    if "accepted" in lowered or "current" in lowered:
        return "ACTIVE_GOVERNING"
    if "proposed" in lowered:
        return "OPEN_PROPOSED"
    return "UNKNOWN"


def _first_paragraph(text: str) -> str:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    for block in blocks:
        if block.startswith("#") and "\n" not in block:
            continue
        lines = [
            line
            for line in block.splitlines()
            if not line.startswith("#") and not line.startswith(">")
        ]
        cleaned = " ".join(line.strip() for line in lines if line.strip())
        if cleaned:
            return cleaned[:400]
    return ""


def locate_demo_estate(start: Path | None = None) -> Path:
    """Resolve ``tests/fixtures/demo/estate`` from a repo-ish start path."""
    here = (start or Path.cwd()).resolve()
    candidates = [here, *here.parents]
    for base in candidates:
        estate = base / "tests" / "fixtures" / "demo" / "estate"
        if (estate / "harbor-api" / ".atlas-project.yaml").is_file():
            return estate
    raise FreshAgentChallengeError("demo-estate-not-found")


def list_estate_projects(estate_root: Path) -> list[str]:
    """Return deterministic project ids under a multi-project estate."""
    root = estate_root.expanduser().resolve()
    if not root.is_dir():
        raise FreshAgentChallengeError(f"estate root is not a directory: {root}")
    found: list[str] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / ".atlas-project.yaml").is_file():
            found.append(_project_id_from_marker(child) or child.name)
    return found


def _scan_project(project_root: Path, project_id: str) -> dict[str, Any]:
    sources: list[dict[str, str]] = []
    decisions: list[dict[str, str]] = []
    postgres_versions: set[str] = set()
    timestamps: list[str] = []
    unknown_fields: list[str] = []
    identity_bits: list[str] = []
    change_bits: list[str] = []
    evidence: list[str] = []

    for path in _iter_markdown(project_root):
        rel = path.relative_to(project_root).as_posix()
        text = _read_text(path)
        sources.append(
            {
                "path": rel,
                "sha256": _sha256_file(path),
                "project_id": project_id,
            }
        )
        evidence.append(rel)
        identity_bits.append(_first_paragraph(text))
        for match in _PG_RE.finditer(text):
            postgres_versions.add(f"PostgreSQL {match.group(1)}")
        for match in _TIMESTAMP_RE.finditer(text):
            timestamps.append(match.group(1))
        auditish = re.search(r"(?i)\bintroduced\b|\badded\b|\b2024 H2\b", text)
        if auditish and "audit" in text.casefold():
            change_bits.append(f"audit logging added ({rel})")
        if re.search(r"(?i)\bunknown\b", text):
            for line in text.splitlines():
                if re.search(r"(?i)\bunknown\b", line) and "|" in line:
                    unknown_fields.append(line.strip())
        if re.search(r"(?i)demo fixture", text):
            identity_bits.append("DEMO FIXTURE")
        for dep in re.findall(
            r"(?i)(?:requires|depends on)\s*[:=]?\s*`?([a-z][a-z0-9-]{2,63})",
            text,
        ):
            identity_bits.append(f"depends:{dep}")
        adr_match = _ADR_NAME_RE.search(path.name) or _ADR_NAME_RE.search(text)
        if adr_match or "decision" in rel.casefold():
            status_match = _STATUS_RE.search(text)
            status_line = status_match.group(1) if status_match else text[:240]
            title_match = _HEADING_RE.search(text)
            title = title_match.group(2).strip() if title_match else path.stem
            adr_id = f"ADR-{int(adr_match.group(1)):03d}" if adr_match else title
            decision_line = ""
            decision_match = re.search(
                r"(?is)##\s+Decision.*?\n+(.+?)(?:\n##|\Z)",
                text,
            )
            if decision_match:
                decision_line = " ".join(decision_match.group(1).split())[:240]
            decisions.append(
                {
                    "id": adr_id,
                    "title": title,
                    "status": _decision_status(status_line + "\n" + text[:800]),
                    "path": rel,
                    "summary": decision_line,
                }
            )

    return {
        "sources": sources,
        "decisions": decisions,
        "postgres_versions": sorted(postgres_versions),
        "timestamps": sorted(set(timestamps)),
        "unknown_fields": unknown_fields,
        "identity_bits": [bit for bit in identity_bits if bit],
        "change_bits": change_bits,
        "evidence": evidence,
    }


def _slot(
    status: SlotStatus,
    text: str,
    evidence: list[str],
) -> dict[str, Any]:
    return {
        "status": status,
        "text": text,
        "evidence": sorted(set(evidence)),
    }


def build_challenge_pack(
    project_root: Path,
    *,
    project_id: str | None = None,
    estate_kind: EstateKind = "DEMO_FIXTURE",
) -> dict[str, Any]:
    """Build a structured context pack from fixture sources.

    The pack carries evidence slices only. It must not contain scoring keys.
    """
    root = project_root.expanduser().resolve()
    if not root.is_dir():
        raise FreshAgentChallengeError(f"project root is not a directory: {root}")
    pid = _safe_project_id(project_id or _project_id_from_marker(root) or root.name)
    scan = _scan_project(root, pid)

    governing = [item for item in scan["decisions"] if item["status"] == "ACTIVE_GOVERNING"]
    superseded = [item for item in scan["decisions"] if item["status"] == "SUPERSEDED"]
    versions: list[str] = list(scan["postgres_versions"])
    conflict = len(versions) >= 2
    change_bits: list[str] = list(scan["change_bits"])
    unknown_fields: list[str] = list(scan["unknown_fields"])
    identity_bits: list[str] = list(scan["identity_bits"])
    evidence: list[str] = list(scan["evidence"])

    readme = root / "README.md"
    readme_bit = _first_paragraph(_read_text(readme)) if readme.is_file() else ""
    display_name = _project_name_from_marker(root) or pid
    demo_stamp = "DEMO FIXTURE" if any(bit == "DEMO FIXTURE" for bit in identity_bits) else ""
    identity_parts = [part for part in (display_name, readme_bit, demo_stamp) if part]
    identity_text = " — ".join(identity_parts) if identity_parts else "UNKNOWN"
    if identity_text == "UNKNOWN":
        identity_slot = _slot("UNKNOWN", "UNKNOWN", [])
    else:
        identity_slot = _slot("known", identity_text, evidence[:3])

    depends = sorted(
        {
            bit.split(":", 1)[1]
            for bit in identity_bits
            if bit.startswith("depends:")
        }
    )
    state_parts: list[str] = []
    if versions:
        state_parts.append("datastore mentions: " + ", ".join(versions))
    if depends:
        state_parts.append("depends on " + ", ".join(depends))
    if conflict:
        state_parts.append("unresolved datastore version conflict")
    if superseded:
        state_parts.append(
            "superseded decisions retained as stale evidence: "
            + ", ".join(item["id"] for item in superseded)
        )
    if unknown_fields:
        state_parts.append("intentional UNKNOWN fields present")
    if not state_parts:
        current_state = _slot("UNKNOWN", "UNKNOWN", [])
    else:
        current_state = _slot(
            "conflict" if conflict else "known",
            "; ".join(state_parts),
            [item["path"] for item in scan["decisions"]] + evidence[:4],
        )

    if change_bits:
        what_changed = _slot("known", "; ".join(change_bits), evidence)
    else:
        what_changed = _slot(
            "UNKNOWN",
            "UNKNOWN (no document-declared change inventory in fixture sources)",
            [],
        )

    if governing:
        gov_text = "; ".join(
            f"{item['id']} ({item['title']}) {item.get('summary') or ''}".strip()
            for item in governing
        )
        governing_slot = _slot(
            "known",
            gov_text,
            [item["path"] for item in governing],
        )
    else:
        governing_slot = _slot("UNKNOWN", "UNKNOWN", [])

    conflict_parts: list[str] = []
    if conflict:
        conflict_parts.append(
            "conflict: " + " vs ".join(versions) + " (do not pick a winner without authority)"
        )
    if unknown_fields:
        conflict_parts.append("UNKNOWN fields: " + " | ".join(unknown_fields[:6]))
    if not conflict_parts:
        unknown_conflict = _slot("UNKNOWN", "UNKNOWN", [])
    else:
        unknown_conflict = _slot(
            "conflict" if conflict else "known",
            "; ".join(conflict_parts),
            evidence,
        )

    attention_parts: list[str] = []
    if conflict:
        attention_parts.append("unresolved datastore conflict requires human disposition")
    if unknown_fields:
        attention_parts.append("do not invent values for intentional UNKNOWN fields")
    if superseded:
        attention_parts.append("do not treat superseded decisions as governing")
    if not attention_parts:
        attention = _slot("UNKNOWN", "UNKNOWN", [])
    else:
        attention = _slot("known", "; ".join(attention_parts), evidence)

    source_health = _slot(
        "known",
        (
            f"fixture-scan source_count={len(scan['sources'])}; "
            "readable=all-scanned; compile_pipeline=ABSENT "
            "(fixture-scan != connect compile health)"
        ),
        [item["path"] for item in scan["sources"]],
    )

    next_parts: list[str] = []
    if conflict:
        next_parts.append(
            "resolve the datastore version conflict via review/disposition; "
            "do not silently prefer PostgreSQL 15 or 16"
        )
    if unknown_fields:
        next_parts.append("leave intentional UNKNOWN operational fields unknown")
    if not next_parts:
        what_next = _slot("UNKNOWN", "UNKNOWN", [])
    else:
        what_next = _slot("known", "; ".join(next_parts), evidence)

    supporting = _slot(
        "known" if evidence else "UNKNOWN",
        "supporting evidence paths: " + ", ".join(sorted(set(evidence)))
        if evidence
        else "UNKNOWN",
        evidence,
    )

    pack: dict[str, Any] = {
        "schema_version": 1,
        "schema": SCHEMA_NAME,
        "package_id": PACKAGE_ID,
        "project_id": pid,
        "estate_kind": estate_kind,
        "truth_boundary": TRUTH_BOUNDARY,
        "slots": {
            "identity": identity_slot,
            "current_state": current_state,
            "what_changed": what_changed,
            "governing_decisions": governing_slot,
            "unknown_conflict": unknown_conflict,
            "attention": attention,
            "source_health": source_health,
            "what_next": what_next,
            "supporting_evidence": supporting,
        },
        "sources": scan["sources"],
        "decisions": scan["decisions"],
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "demo_fixture_ne_authentic_pilot": True,
            "model_output_ne_authority": True,
            "hidden_benchmark_answers": False,
            "lens_is_authority": False,
            "network_required": False,
        },
    }
    _assert_no_hidden_benchmark(pack)
    return pack


def _walk_keys(payload: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.add(str(key))
            keys.update(_walk_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            keys.update(_walk_keys(item))
    return keys


def _assert_no_hidden_benchmark(pack: dict[str, Any]) -> None:
    found = _walk_keys(pack) & _HIDDEN_PACK_KEYS
    if found:
        raise FreshAgentChallengeError(
            "hidden-benchmark-in-pack:" + ",".join(sorted(found))
        )


def pack_has_hidden_benchmark(pack: dict[str, Any]) -> bool:
    """Return True when a pack illegally embeds scoring keys."""
    return bool(_walk_keys(pack) & _HIDDEN_PACK_KEYS)


def expected_catalog_for(project_id: str) -> ExpectedCatalog:
    """Return the fixture-derived scoring catalog for a known demo project.

    Catalog tokens come from canonical harbor-* fixture files, not model taste.
    Self-dogfood of this repository is labeled DEMO_FIXTURE != AUTHENTIC_PILOT.
    """
    pid = _safe_project_id(project_id)
    if pid == "harbor-api":
        return ExpectedCatalog(
            project_id=pid,
            estate_kind="DEMO_FIXTURE",
            slots=(
                SlotExpectation(
                    slot="identity",
                    required_tokens=("Harbor API", "DEMO FIXTURE"),
                    leak_tokens=("on-call pager rotation", "Disaster-recovery RPO"),
                    evidence_paths=("README.md",),
                ),
                SlotExpectation(
                    slot="current_state",
                    required_tokens=("PostgreSQL",),
                    forbidden_tokens=("managed MySQL as current",),
                    evidence_paths=("ARCHITECTURE.md", "src/RUNTIME.md"),
                ),
                SlotExpectation(
                    slot="what_changed",
                    required_tokens=("audit",),
                    evidence_paths=("docs/audit-logging.md",),
                ),
                SlotExpectation(
                    slot="governing_decisions",
                    required_tokens=("ADR-001", "PostgreSQL 15"),
                    forbidden_tokens=("ADR-002", "managed MySQL"),
                    evidence_paths=("docs/ADR-001-database.md",),
                ),
                SlotExpectation(
                    slot="unknown_conflict",
                    required_tokens=("PostgreSQL 15", "PostgreSQL 16", "conflict"),
                    evidence_paths=(
                        "docs/datastore-architecture.md",
                        "src/datastore-runtime.md",
                    ),
                ),
                SlotExpectation(
                    slot="attention",
                    required_tokens=("conflict",),
                    forbidden_tokens=("ADR-002 is governing",),
                    evidence_paths=("src/RUNTIME.md",),
                ),
                SlotExpectation(
                    slot="source_health",
                    required_tokens=("source_count",),
                    evidence_paths=("README.md",),
                ),
                SlotExpectation(
                    slot="what_next",
                    required_tokens=("conflict",),
                    forbidden_tokens=("prefer PostgreSQL 16 as winner",),
                    evidence_paths=("src/RUNTIME.md",),
                ),
                SlotExpectation(
                    slot="supporting_evidence",
                    required_tokens=("ADR-001", "RUNTIME"),
                    evidence_paths=("docs/ADR-001-database.md", "src/RUNTIME.md"),
                ),
            ),
        )
    if pid == "harbor-portal":
        return ExpectedCatalog(
            project_id=pid,
            estate_kind="DEMO_FIXTURE",
            slots=(
                SlotExpectation(
                    slot="identity",
                    required_tokens=("Harbor Portal", "DEMO FIXTURE"),
                    leak_tokens=("PostgreSQL 15", "PostgreSQL 16", "on-call pager"),
                    evidence_paths=("README.md",),
                ),
                SlotExpectation(
                    slot="current_state",
                    required_tokens=("harbor-api",),
                    forbidden_tokens=("PostgreSQL 15", "PostgreSQL 16"),
                    leak_tokens=("PostgreSQL 15", "PostgreSQL 16"),
                    evidence_paths=("DEPENDENCIES.md",),
                ),
                SlotExpectation(
                    slot="what_changed",
                    unknown_required=True,
                    evidence_paths=(),
                ),
                SlotExpectation(
                    slot="governing_decisions",
                    unknown_required=True,
                    leak_tokens=("ADR-001", "PostgreSQL 15"),
                    evidence_paths=(),
                ),
                SlotExpectation(
                    slot="unknown_conflict",
                    unknown_required=True,
                    leak_tokens=("PostgreSQL 16",),
                    evidence_paths=(),
                ),
                SlotExpectation(
                    slot="attention",
                    unknown_required=True,
                    evidence_paths=(),
                ),
                SlotExpectation(
                    slot="source_health",
                    required_tokens=("source_count",),
                    evidence_paths=("README.md",),
                ),
                SlotExpectation(
                    slot="what_next",
                    unknown_required=True,
                    evidence_paths=(),
                ),
                SlotExpectation(
                    slot="supporting_evidence",
                    required_tokens=("README.md",),
                    leak_tokens=("datastore-runtime.md",),
                    evidence_paths=("README.md",),
                ),
            ),
        )
    if pid == "harbor-ops":
        return ExpectedCatalog(
            project_id=pid,
            estate_kind="DEMO_FIXTURE",
            slots=(
                SlotExpectation(
                    slot="identity",
                    required_tokens=("Harbor Ops", "unknown"),
                    leak_tokens=("PostgreSQL 16", "API key header"),
                    evidence_paths=("README.md",),
                ),
                SlotExpectation(
                    slot="current_state",
                    required_tokens=("UNKNOWN",),
                    leak_tokens=("PostgreSQL 15",),
                    evidence_paths=("INVENTORY.md",),
                ),
                SlotExpectation(
                    slot="what_changed",
                    unknown_required=True,
                    evidence_paths=(),
                ),
                SlotExpectation(
                    slot="governing_decisions",
                    unknown_required=True,
                    leak_tokens=("ADR-001",),
                    evidence_paths=(),
                ),
                SlotExpectation(
                    slot="unknown_conflict",
                    required_tokens=("unknown",),
                    evidence_paths=("INVENTORY.md",),
                ),
                SlotExpectation(
                    slot="attention",
                    required_tokens=("UNKNOWN",),
                    evidence_paths=("INVENTORY.md",),
                ),
                SlotExpectation(
                    slot="source_health",
                    required_tokens=("source_count",),
                    evidence_paths=("README.md",),
                ),
                SlotExpectation(
                    slot="what_next",
                    required_tokens=("UNKNOWN",),
                    evidence_paths=("INVENTORY.md",),
                ),
                SlotExpectation(
                    slot="supporting_evidence",
                    required_tokens=("INVENTORY.md",),
                    evidence_paths=("INVENTORY.md",),
                ),
            ),
        )
    if pid in {"project-atlas", "atlas"}:
        return ExpectedCatalog(
            project_id=pid,
            estate_kind="SELF_DOGFOOD_DEMO",
            slots=(
                SlotExpectation(
                    slot="identity",
                    required_tokens=("persistent brain", "Coder Alpha"),
                    evidence_paths=("docs/product/CODER-ALPHA-NORTH-STAR.md",),
                ),
                SlotExpectation(
                    slot="what_changed",
                    unknown_required=True,
                ),
                SlotExpectation(
                    slot="unknown_conflict",
                    required_tokens=("UNKNOWN",),
                ),
            ),
        )
    raise FreshAgentChallengeError(f"no-canonical-catalog:{pid}")


def extract_answers_from_pack(pack: dict[str, Any]) -> dict[str, ExtractedAnswer]:
    """Deterministic pack-only extractor. No model, no network, no prompt tricks."""
    slots = pack.get("slots")
    if not isinstance(slots, dict):
        raise FreshAgentChallengeError("pack-slots-missing")
    extracted: dict[str, ExtractedAnswer] = {}
    for name in REQUIRED_SLOTS:
        raw = slots.get(name)
        if not isinstance(raw, dict):
            extracted[name] = ExtractedAnswer(name, "UNKNOWN", "UNKNOWN", ())
            continue
        status_raw = str(raw.get("status") or "UNKNOWN")
        status: SlotStatus
        if status_raw == "known":
            status = "known"
        elif status_raw == "conflict":
            status = "conflict"
        else:
            status = "UNKNOWN"
        text = str(raw.get("text") or "UNKNOWN").strip() or "UNKNOWN"
        evidence_raw = raw.get("evidence")
        evidence = (
            tuple(str(item) for item in evidence_raw)
            if isinstance(evidence_raw, list)
            else ()
        )
        if status == "UNKNOWN":
            text = "UNKNOWN" if text.casefold().startswith("unknown") else text
        extracted[name] = ExtractedAnswer(name, status, text, evidence)
    return extracted


def _slot_covered(answer: ExtractedAnswer) -> bool:
    if answer.status == "UNKNOWN":
        return True
    return bool(answer.text.strip()) and bool(answer.evidence or answer.text != "UNKNOWN")


def _score_slot(answer: ExtractedAnswer, expected: SlotExpectation | None) -> SlotScore:
    if expected is None:
        return SlotScore(
            slot=answer.slot,
            covered=_slot_covered(answer),
            accurate=True,
            stale=False,
            unknown_honest=None,
            leak_hits=(),
            notes="no-catalog-expectation",
        )
    blob = f"{answer.status} {answer.text} {' '.join(answer.evidence)}"
    leak_hits = tuple(token for token in expected.leak_tokens if _contains(blob, token))
    if expected.unknown_required:
        honest = answer.status == "UNKNOWN" or _norm(answer.text).startswith("unknown")
        invented = not honest
        return SlotScore(
            slot=answer.slot,
            covered=True,
            accurate=honest,
            stale=False,
            unknown_honest=honest,
            leak_hits=leak_hits,
            notes="invented-over-unknown" if invented else "unknown-honest",
        )
    missing = [token for token in expected.required_tokens if not _contains(blob, token)]
    forbidden = [token for token in expected.forbidden_tokens if _contains(blob, token)]
    stale = bool(forbidden)
    accurate = not missing and not forbidden
    covered = bool(answer.text.strip()) and answer.text != "UNKNOWN"
    if expected.required_tokens and answer.status == "UNKNOWN":
        covered = False
        accurate = False
    return SlotScore(
        slot=answer.slot,
        covered=covered or accurate,
        accurate=accurate,
        stale=stale,
        unknown_honest=None,
        leak_hits=leak_hits,
        notes=(
            "ok"
            if accurate and not leak_hits
            else f"missing={missing}; forbidden={forbidden}"
        ),
    )


def score_challenge(
    pack: dict[str, Any],
    catalog: ExpectedCatalog,
    *,
    answers: dict[str, ExtractedAnswer] | None = None,
) -> ChallengeScore:
    """Score pack-only answers against the fixture catalog.

    ``answers`` may be supplied (future LLM path). Core scoring uses the
    deterministic extractor when omitted. No network is consulted.
    """
    if pack.get("project_id") != catalog.project_id:
        raise FreshAgentChallengeError("pack-catalog-project-mismatch")
    hidden = pack_has_hidden_benchmark(pack)
    extracted = answers or extract_answers_from_pack(pack)
    expected = catalog.by_slot()
    slot_scores = tuple(
        _score_slot(extracted[name], expected.get(name)) for name in REQUIRED_SLOTS
    )
    covered = sum(1 for item in slot_scores if item.covered)
    accurate = sum(1 for item in slot_scores if item.accurate)
    stale = sum(1 for item in slot_scores if item.stale)
    unknown_items = [item for item in slot_scores if item.unknown_honest is not None]
    unknown_ok = sum(1 for item in unknown_items if item.unknown_honest)
    leaks = sum(len(item.leak_hits) for item in slot_scores)
    coverage = covered / len(REQUIRED_SLOTS)
    accuracy = accurate / len(REQUIRED_SLOTS)
    stale_rate = stale / len(REQUIRED_SLOTS)
    honesty = (unknown_ok / len(unknown_items)) if unknown_items else 1.0
    reexplain = (not hidden) and (accuracy < 1.0 or coverage < 1.0 or leaks > 0)
    return ChallengeScore(
        project_id=catalog.project_id,
        estate_kind=catalog.estate_kind,
        context_coverage=coverage,
        context_accuracy=accuracy,
        stale_context_rate=stale_rate,
        unknown_honesty=honesty,
        cross_project_leak_count=leaks,
        reexplanation_required=reexplain,
        slot_scores=slot_scores,
        hidden_benchmark_in_pack=hidden,
        network_required=False,
        honesty={
            "authentic_pilot": False,
            "demo_fixture_ne_authentic_pilot": True,
            "model_output_ne_authority": True,
            "hidden_benchmark_answers": hidden,
            "network_required": False,
        },
    )


def score_as_dict(score: ChallengeScore) -> dict[str, Any]:
    """Deterministic JSON-ready score (no wall-clock)."""
    return {
        "schema_version": 1,
        "schema": SCHEMA_NAME,
        "package_id": PACKAGE_ID,
        "project_id": score.project_id,
        "estate_kind": score.estate_kind,
        "metrics": {
            "CONTEXT_COVERAGE": score.context_coverage,
            "CONTEXT_ACCURACY": score.context_accuracy,
            "STALE_CONTEXT_RATE": score.stale_context_rate,
            "UNKNOWN_HONESTY": score.unknown_honesty,
            "CROSS_PROJECT_LEAK_COUNT": score.cross_project_leak_count,
        },
        "reexplanation_required": score.reexplanation_required,
        "hidden_benchmark_in_pack": score.hidden_benchmark_in_pack,
        "network_required": score.network_required,
        "slots": [
            {
                "slot": item.slot,
                "covered": item.covered,
                "accurate": item.accurate,
                "stale": item.stale,
                "unknown_honest": item.unknown_honest,
                "leak_hits": list(item.leak_hits),
                "notes": item.notes,
            }
            for item in score.slot_scores
        ],
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": GENERATOR_ID},
        "honesty": score.honesty,
    }


def write_challenge_receipt(vault: Path, score: ChallengeScore) -> Path:
    """Write a non-authoritative ops receipt under ``generated/ops/fresh-agent``."""
    vault_path = vault.expanduser().resolve()
    if not vault_path.is_dir():
        raise FreshAgentChallengeError(f"vault is not a directory: {vault_path}")
    payload = score_as_dict(score)
    out = vault_path / RECEIPT_DIR / f"{score.project_id}.json"
    _write_atomic(
        out,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return out


def run_estate_challenge(
    estate_root: Path,
    *,
    vault: Path | None = None,
    project_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Score every selected estate project. Optional self-dogfood is separate."""
    estate = estate_root.expanduser().resolve()
    ids = project_ids or list_estate_projects(estate)
    reports: list[dict[str, Any]] = []
    for pid in ids:
        pack = build_challenge_pack(estate / pid, project_id=pid)
        catalog = expected_catalog_for(pid)
        score = score_challenge(pack, catalog)
        if vault is not None:
            write_challenge_receipt(vault, score)
        reports.append(
            {
                "project_id": pid,
                "pack_project_id": pack["project_id"],
                "hidden_benchmark_in_pack": pack_has_hidden_benchmark(pack),
                "score": score_as_dict(score),
            }
        )
    leak_total = sum(
        int(item["score"]["metrics"]["CROSS_PROJECT_LEAK_COUNT"]) for item in reports
    )
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "estate_kind": "DEMO_FIXTURE",
        "projects": reports,
        "metrics": {
            "CROSS_PROJECT_LEAK_COUNT": leak_total,
        },
        "honesty": {
            "authentic_pilot": False,
            "demo_fixture_ne_authentic_pilot": True,
            "model_output_ne_authority": True,
        },
        "generated": {"by": GENERATOR_ID},
        "truth_boundary": TRUTH_BOUNDARY,
    }


def adapt_generated_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Adapt an Atlas agent-context JSON export into challenge-pack slots.

    Used for optional self-dogfood. Does not invent missing fields.
    """
    project_id = _safe_project_id(str(payload.get("project_id") or "unknown"))
    brief = payload.get("brief") if isinstance(payload.get("brief"), dict) else {}
    markdown = str(payload.get("markdown") or "")
    purpose = str(brief.get("purpose") or "") if isinstance(brief, dict) else ""
    identity_text = purpose or markdown[:400] or "UNKNOWN"
    identity_status: SlotStatus = "UNKNOWN" if identity_text == "UNKNOWN" else "known"

    def _from_brief(*keys: str) -> tuple[SlotStatus, str]:
        for key in keys:
            value = brief.get(key) if isinstance(brief, dict) else None
            if isinstance(value, str) and value.strip():
                status: SlotStatus = (
                    "UNKNOWN" if value.casefold().startswith("unknown") else "known"
                )
                return status, value
        return "UNKNOWN", "UNKNOWN"

    changed_status, changed_text = _from_brief("changed", "what_changed")
    decisions_status, decisions_text = _from_brief("decisions", "governing_decisions")
    unknown_status, unknown_text = _from_brief("unknown", "conflicts")
    next_status, next_text = _from_brief("suggested_next_work", "next")
    attention_raw = payload.get("attention")
    attention_text = (
        json.dumps(attention_raw, sort_keys=True)
        if isinstance(attention_raw, dict)
        else "UNKNOWN"
    )
    health_raw = payload.get("source_health")
    health_text = (
        json.dumps(health_raw, sort_keys=True)
        if isinstance(health_raw, dict)
        else "UNKNOWN"
    )
    pack = {
        "schema_version": 1,
        "schema": SCHEMA_NAME,
        "package_id": PACKAGE_ID,
        "project_id": project_id,
        "estate_kind": "SELF_DOGFOOD_DEMO",
        "truth_boundary": TRUTH_BOUNDARY,
        "slots": {
            "identity": _slot(identity_status, identity_text, ["generated/ops/agent-context"]),
            "current_state": _slot(*_from_brief("state", "current_state"), ["brief"]),
            "what_changed": _slot(changed_status, changed_text, ["brief"]),
            "governing_decisions": _slot(decisions_status, decisions_text, ["brief"]),
            "unknown_conflict": _slot(unknown_status, unknown_text, ["brief"]),
            "attention": _slot(
                "UNKNOWN" if attention_text == "UNKNOWN" else "known",
                attention_text,
                ["attention"],
            ),
            "source_health": _slot(
                "UNKNOWN" if health_text == "UNKNOWN" else "known",
                health_text,
                ["source_health"],
            ),
            "what_next": _slot(next_status, next_text, ["brief"]),
            "supporting_evidence": _slot(
                "known" if markdown else "UNKNOWN",
                markdown[:800] if markdown else "UNKNOWN",
                ["markdown"],
            ),
        },
        "sources": [],
        "decisions": [],
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "demo_fixture_ne_authentic_pilot": True,
            "model_output_ne_authority": True,
            "hidden_benchmark_answers": False,
            "self_dogfood": True,
        },
    }
    _assert_no_hidden_benchmark(pack)
    return pack
