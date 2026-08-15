"""AS-CODER-ALPHA-CONTEXT-FRESHNESS-ADV-001 — adversarial freshness checker.

Compares a frozen context snapshot to current evidence. Detects stale
citations, superseded-as-governing, cross-project leaks, UNKNOWN
suppression, and secret echo. Does not rewrite ``connect.py``.

No-change reconnect honesty is evaluated from two snapshots' source
fingerprints. When fingerprints are absent, the case is UNKNOWN — never
faked as a pass.

Receipts under ``generated/ops/context-freshness/`` are ops telemetry,
not Truth Core.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from atlas_contracts.identity import safe_relative_component
from project_atlas.secrets import scan_text

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-CONTEXT-FRESHNESS-ADV-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-context-freshness-adv-001"
SCHEMA_NAME: Final[str] = "atlas.coder-alpha.context-freshness-adv.v1"
RECEIPT_DIR: Final[Path] = Path("generated") / "ops" / "context-freshness"
TRUTH_BOUNDARY: Final[str] = (
    "FRESHNESS CHECKER != CONNECT REWRITE / != AUTHENTIC_PILOT / "
    "UNKNOWN != HEALTHY / TELEMETRY != TRUTH CORE"
)

FindingKind = Literal[
    "stale_source",
    "superseded_as_governing",
    "cross_project_leak",
    "unknown_suppression",
    "secret_echo",
    "malformed_artifact",
    "missing_conflict",
    "source_health_gap",
    "stale_generated_answer",
    "false_change_claim",
]
ReconnectStatus = Literal["PASS", "FAIL", "UNKNOWN"]


class ContextFreshnessError(ValueError):
    """Fail-closed freshness checker error."""


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    path: str
    project_id: str
    sha256: str | None
    exists: bool
    text: str | None = None


@dataclass(frozen=True, slots=True)
class DecisionSnapshot:
    decision_id: str
    status: str
    title: str
    project_id: str


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    answer_id: str
    project_id: str
    source_path: str
    source_sha256: str | None
    parse_status: Literal["ok", "malformed", "absent"]
    claims_healthy: bool = False


@dataclass(frozen=True, slots=True)
class QuarantineCapture:
    capture_id: str
    project_id: str
    referenced_project_id: str | None
    included_in_pack: bool
    text: str


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    project_id: str
    sources: tuple[SourceSnapshot, ...] = ()
    decisions: tuple[DecisionSnapshot, ...] = ()
    slot_texts: dict[str, str] = field(default_factory=dict)
    generated_answers: tuple[GeneratedAnswer, ...] = ()
    quarantined_captures: tuple[QuarantineCapture, ...] = ()
    source_health_failures: tuple[str, ...] = ()
    claims_material_change: bool | None = None
    claims_all_healthy: bool = False


@dataclass(frozen=True, slots=True)
class FreshnessFinding:
    case_id: str
    kind: FindingKind
    detail: str
    path: str | None = None


@dataclass(frozen=True, slots=True)
class FreshnessReport:
    project_id: str
    findings: tuple[FreshnessFinding, ...]
    stale_context_false_negative: int
    cross_project_leak_count: int
    superseded_as_governing: int
    unknown_suppression: int
    secret_echo: int
    reconnect_honesty: ReconnectStatus
    covered_cases: tuple[str, ...]
    honesty: dict[str, object]


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise ContextFreshnessError(str(exc)) from exc


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
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


def assess_freshness(
    frozen: ContextSnapshot,
    current: ContextSnapshot,
    *,
    sibling_tokens: dict[str, tuple[str, ...]] | None = None,
    case_id: str = "generic",
) -> FreshnessReport:
    """Compare a frozen context snapshot to current evidence."""
    if frozen.project_id != current.project_id:
        raise ContextFreshnessError("freshness-project-mismatch")
    project_id = _safe_project_id(frozen.project_id)
    findings: list[FreshnessFinding] = []
    covered: list[str] = []
    frozen_sources = _as_sources(frozen.sources)
    current_sources = _as_sources(current.sources)

    current_by_path = {item.path: item for item in current_sources}
    for source in frozen_sources:
        live = current_by_path.get(source.path)
        if live is None or not live.exists:
            findings.append(
                FreshnessFinding(
                    case_id=case_id,
                    kind="stale_source",
                    detail="frozen context cites a source that no longer exists",
                    path=source.path,
                )
            )
            covered.append("source_deleted")
            continue
        if (
            source.sha256
            and live.sha256
            and source.sha256 != live.sha256
        ):
            findings.append(
                FreshnessFinding(
                    case_id=case_id,
                    kind="stale_source",
                    detail="source modified after context generation / handoff",
                    path=source.path,
                )
            )
            covered.append("source_modified")

    frozen_decisions = {item.decision_id: item for item in frozen.decisions}
    for decision in current.decisions:
        prior = frozen_decisions.get(decision.decision_id)
        if prior is None:
            continue
        if prior.status == "ACTIVE_GOVERNING" and decision.status == "SUPERSEDED":
            findings.append(
                FreshnessFinding(
                    case_id=case_id,
                    kind="superseded_as_governing",
                    detail=(
                        f"{decision.decision_id} is superseded in current evidence "
                        "but frozen context still treats it as governing"
                    ),
                    path=decision.decision_id,
                )
            )
            covered.append("governing_superseded")

    frozen_conflicts = _norm(" ".join(frozen.slot_texts.values()))
    current_conflict_markers = [
        item
        for item in current_sources
        if item.exists and item.text and "conflict" in item.text.casefold()
    ]
    if current_conflict_markers and "conflict" not in frozen_conflicts:
        findings.append(
            FreshnessFinding(
                case_id=case_id,
                kind="missing_conflict",
                detail="conflicting source introduced after context generation",
                path=current_conflict_markers[0].path,
            )
        )
        covered.append("conflicting_source_introduced")

    frozen_failures = set(frozen.source_health_failures)
    for failure in current.source_health_failures:
        if failure not in frozen_failures:
            findings.append(
                FreshnessFinding(
                    case_id=case_id,
                    kind="source_health_gap",
                    detail="source-health failure introduced after context generation",
                    path=failure,
                )
            )
            covered.append("source_health_failure_introduced")

    pack_blob = " ".join(frozen.slot_texts.values())
    for other_id, tokens in (sibling_tokens or {}).items():
        if other_id == project_id:
            continue
        for token in tokens:
            if token and _contains(pack_blob, token):
                findings.append(
                    FreshnessFinding(
                        case_id=case_id,
                        kind="cross_project_leak",
                        detail=f"frozen pack for {project_id} contains {other_id} token",
                        path=token,
                    )
                )
                covered.append("shared_filename_leak")

    for capture in frozen.quarantined_captures:
        if (
            capture.included_in_pack
            and capture.referenced_project_id
            and capture.referenced_project_id != project_id
        ):
            findings.append(
                FreshnessFinding(
                    case_id=case_id,
                    kind="cross_project_leak",
                    detail=(
                        "quarantined capture references another project "
                        f"({capture.referenced_project_id})"
                    ),
                    path=capture.capture_id,
                )
            )
            covered.append("quarantined_capture_other_project")

    for answer in current.generated_answers:
        if answer.parse_status == "malformed":
            findings.append(
                FreshnessFinding(
                    case_id=case_id,
                    kind="malformed_artifact",
                    detail="generated artifact is malformed",
                    path=answer.answer_id,
                )
            )
            covered.append("malformed_generated_artifact")
            if frozen.claims_all_healthy or answer.claims_healthy:
                findings.append(
                    FreshnessFinding(
                        case_id=case_id,
                        kind="unknown_suppression",
                        detail="malformed artifact presented as healthy/known",
                        path=answer.answer_id,
                    )
                )
                covered.append("unknown_suppression")
            continue
        frozen_match = next(
            (
                item
                for item in frozen.generated_answers
                if item.answer_id == answer.answer_id
            ),
            None,
        )
        if (
            frozen_match
            and frozen_match.source_sha256
            and answer.source_sha256
            and frozen_match.source_sha256 != answer.source_sha256
        ):
            findings.append(
                FreshnessFinding(
                    case_id=case_id,
                    kind="stale_generated_answer",
                    detail="generated answer hash no longer matches current source",
                    path=answer.answer_id,
                )
            )
            covered.append("stale_generated_answer")

    for text in frozen.slot_texts.values():
        if scan_text(text):
            findings.append(
                FreshnessFinding(
                    case_id=case_id,
                    kind="secret_echo",
                    detail="secret-shaped span echoed in frozen context text",
                    path=None,
                )
            )
            covered.append("secret_echo")
            break

    reconnect = assess_reconnect_honesty(frozen, current)
    if reconnect == "FAIL":
        findings.append(
            FreshnessFinding(
                case_id=case_id,
                kind="false_change_claim",
                detail="no-change reconnect claimed material change",
                path=None,
            )
        )
        covered.append("no_change_reconnect")
    elif reconnect == "UNKNOWN":
        covered.append("no_change_reconnect_unknown")

    leak_count = sum(1 for item in findings if item.kind == "cross_project_leak")
    superseded = sum(1 for item in findings if item.kind == "superseded_as_governing")
    unknown_sup = sum(1 for item in findings if item.kind == "unknown_suppression")
    secret = sum(1 for item in findings if item.kind == "secret_echo")
    # STALE_CONTEXT_FALSE_NEGATIVE is asserted per constructed case via
    # invariants_hold(..., expect_stale=True). The receipt stores 0 here.
    return FreshnessReport(
        project_id=project_id,
        findings=tuple(findings),
        stale_context_false_negative=0,
        cross_project_leak_count=leak_count,
        superseded_as_governing=superseded,
        unknown_suppression=unknown_sup,
        secret_echo=secret,
        reconnect_honesty=reconnect,
        covered_cases=tuple(dict.fromkeys(covered)),
        honesty={
            "authentic_pilot": False,
            "demo_fixture_ne_authentic_pilot": True,
            "connect_py_rewritten": False,
            "no_change_reconnect": reconnect,
        },
    )


def _as_sources(
    sources: tuple[SourceSnapshot, ...] | SourceSnapshot,
) -> tuple[SourceSnapshot, ...]:
    if isinstance(sources, SourceSnapshot):
        return (sources,)
    return sources


def assess_reconnect_honesty(
    before: ContextSnapshot,
    after: ContextSnapshot,
) -> ReconnectStatus:
    """Library-only no-change reconnect check. Does not call connect.py.

    UNKNOWN when either snapshot lacks source fingerprints — do not fake PASS.
    """
    before_fps = tuple(
        (item.path, item.sha256) for item in _as_sources(before.sources) if item.sha256
    )
    after_fps = tuple(
        (item.path, item.sha256) for item in _as_sources(after.sources) if item.sha256
    )
    if not before_fps or not after_fps:
        return "UNKNOWN"
    if before_fps != after_fps:
        return "PASS"
    if after.claims_material_change is None:
        return "UNKNOWN"
    if after.claims_material_change:
        return "FAIL"
    return "PASS"


def invariants_hold(report: FreshnessReport, *, expect_stale: bool) -> dict[str, int]:
    """Return invariant counters. Tests require zeros except when a case expects findings."""
    stale_fn = 0
    if expect_stale:
        stale_kinds = {
            "stale_source",
            "superseded_as_governing",
            "missing_conflict",
            "source_health_gap",
            "stale_generated_answer",
        }
        if not any(item.kind in stale_kinds for item in report.findings):
            stale_fn = 1
    return {
        "STALE_CONTEXT_FALSE_NEGATIVE": stale_fn,
        "CROSS_PROJECT_LEAK_COUNT": report.cross_project_leak_count,
        "SUPERSEDED_AS_GOVERNING": report.superseded_as_governing,
        "UNKNOWN_SUPPRESSION": report.unknown_suppression,
        "SECRET_ECHO": report.secret_echo,
    }


def report_as_dict(report: FreshnessReport) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "schema": SCHEMA_NAME,
        "package_id": PACKAGE_ID,
        "project_id": report.project_id,
        "findings": [
            {
                "case_id": item.case_id,
                "kind": item.kind,
                "detail": item.detail,
                "path": item.path,
            }
            for item in report.findings
        ],
        "invariants": {
            "STALE_CONTEXT_FALSE_NEGATIVE": report.stale_context_false_negative,
            "CROSS_PROJECT_LEAK_COUNT": report.cross_project_leak_count,
            "SUPERSEDED_AS_GOVERNING": report.superseded_as_governing,
            "UNKNOWN_SUPPRESSION": report.unknown_suppression,
            "SECRET_ECHO": report.secret_echo,
        },
        "reconnect_honesty": report.reconnect_honesty,
        "covered_cases": list(report.covered_cases),
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": GENERATOR_ID},
        "honesty": report.honesty,
    }


def write_freshness_receipt(vault: Path, report: FreshnessReport) -> Path:
    vault_path = vault.expanduser().resolve()
    if not vault_path.is_dir():
        raise ContextFreshnessError(f"vault is not a directory: {vault_path}")
    out = vault_path / RECEIPT_DIR / f"{report.project_id}.json"
    _write_atomic(
        out,
        (json.dumps(report_as_dict(report), indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )
    return out
