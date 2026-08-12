"""AS-OPT-GATE-001 — governed experiment and promotion boundary.

Trust boundary required before Atlas-OPT may become eligible to wake. This
module does not wake OPT, launch AutoLab, mutate retrieval/prompts/models, merge
candidates, or deploy anything.

Promotion decisions are PROMOTE_ELIGIBLE | REJECT | INVALID_EXPERIMENT.
PROMOTE_ELIGIBLE is not MERGED, not DEPLOYED, and not AUTHORITATIVE.

Scoring authority is engine-owned:
  * public/regression cases → ``eval_substrate.score_cases``
  * hidden holdout aggregates → out-of-process ``ScoringBrokerSession.submit``

Caller-supplied quality scores and gate outcomes are ignored.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas import eval_substrate, scoring_broker, scoring_broker_server
from project_atlas.eval_substrate import load_cases, public_root, regression_root, score_cases
from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.scoring_broker import ScoringBrokerError, ScoringBrokerSession
from project_atlas.secrets import scan_text

PACKAGE_ID: Final[str] = "AS-OPT-GATE-001"
SCHEMA_KIND: Final[str] = "opt-experiment-receipt"
RECEIPT_SCHEMA_VERSION: Final[int] = 1
TRUTH_BOUNDARY: Final[str] = (
    "OPT-GATE ≠ OPT / ≠ AUTOLAB / ≠ RL / ≠ PRIME / ≠ MERGE / ≠ DEPLOY / ≠ AUTHORITY"
)
ATLAS_OPT_WAKE_GATE: Final[str] = "CLOSED"

POLICY_REL: Final[Path] = Path("fixtures") / "eval" / "opt-gate"

HardGateName = Literal[
    "security",
    "provenance_integrity",
    "authority_integrity",
    "unknown_honesty",
    "conflict_honesty",
    "evidence_integrity",
    "determinism",
    "project_isolation",
    "holdout_isolation",
]
GateResult = Literal["PASS", "FAIL"]
PromotionDecision = Literal["PROMOTE_ELIGIBLE", "REJECT", "INVALID_EXPERIMENT"]

REQUIRED_HARD_GATES: Final[tuple[HardGateName, ...]] = (
    "security",
    "provenance_integrity",
    "authority_integrity",
    "unknown_honesty",
    "conflict_honesty",
    "evidence_integrity",
    "determinism",
    "project_isolation",
    "holdout_isolation",
)

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_OPAQUE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_HOLD_ID_RE = re.compile(r"^EV-HOLD-", re.IGNORECASE)
_SAFE_REF_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")

_UNKNOWN_PREDICTED = frozenset({"", "unknown"})
_CONFLICT_PREDICTED = frozenset({"", "conflict", "unresolved"})

_AUTHORIZED_PARAMETER_KEYS = frozenset({"answer_style", "max_answers"})
_FORBIDDEN_CONFIG_KEYS = frozenset(
    {
        "evaluator",
        "holdout",
        "scoring_policy",
        "hard_gate_policy",
        "thresholds",
        "promotion",
        "baseline",
        "expected",
        "wake_opt",
        "atlas_opt",
        "quality_score",
        "hard_gates",
        "hard_gate_outcomes",
        "promotion_decision",
        "opt_woken",
        "expected_map",
        "holdout_expected",
        "open_eligible",
        "atlas_eval_scoring_capability",
        "atlas_eval_holdout_expected_path",
        "promote_authority",
        "subjective_score",
        "rl",
        "prime",
    }
)

_OPT_WAKE_KEYS = frozenset(
    {
        "wake_opt",
        "wake_atlas_opt",
        "enable_opt",
        "atlas_opt_001",
        "atlas_opt_002",
        "opt_001",
        "opt_002",
        "open_eligible",
    }
)

_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "candidate-config-malformed",
        "baseline-config-malformed",
        "threshold-missing",
        "evaluator-digest-missing",
        "gate-missing",
        "gate-unknown",
        "receipt-invalid",
        "receipt-schema-mismatch",
        "holdout-broker-unavailable",
        "scoring-broker-partial-failure",
        "sealed-component-changed",
        "experiment-id-invalid",
        "repo-identity-invalid",
        "opt-gated",
        "forbidden-claim",
        "honesty-catalog-missing",
        "public-dataset-missing",
        "hard-gate-policy-invalid",
        "scoring-policy-invalid",
        "policy-missing",
        "arm-invalid",
    }
)

class OptGateError(RuntimeError):
    """Fail-closed opt-gate error. Message is a fixed code — never a secret."""

    def __init__(self, code: str) -> None:
        safe = code if code in _ERROR_CODES else "receipt-invalid"
        super().__init__(safe)
        self.code = safe


@dataclass(frozen=True)
class HonestyAnswer:
    """One candidate answer used only for hard-gate honesty checks."""

    case_id: str
    status: str
    predicted: str
    citations: tuple[str, ...]
    project_id: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ArmOutput:
    """Frozen candidate/baseline outputs. Holdout keys must be opaque ids."""

    public_predictions: tuple[tuple[str, str], ...]
    honesty_answers: tuple[HonestyAnswer, ...]
    holdout_predictions: tuple[tuple[str, str], ...]
    replay_public_predictions: tuple[tuple[str, str], ...] | None
    replay_honesty_answers: tuple[HonestyAnswer, ...] | None
    claimed_quality_score: float | None
    authority_promoted: bool


@dataclass(frozen=True)
class ScoreCounts:
    cases_scored: int
    cases_matched: int
    cases_missed: int

    def as_dict(self) -> dict[str, int]:
        return {
            "cases_scored": self.cases_scored,
            "cases_matched": self.cases_matched,
            "cases_missed": self.cases_missed,
        }


def _score_counts_from(raw: Any) -> ScoreCounts:
    if not isinstance(raw, dict):
        raise OptGateError("receipt-invalid")
    try:
        return ScoreCounts(
            cases_scored=int(raw["cases_scored"]),
            cases_matched=int(raw["cases_matched"]),
            cases_missed=int(raw["cases_missed"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OptGateError("receipt-invalid") from exc


@dataclass(frozen=True)
class OptGatePolicies:
    scoring: dict[str, Any]
    hard_gates: dict[str, Any]
    thresholds: dict[str, Any]
    honesty_catalog: dict[str, Any]
    policy_root: Path


@dataclass(frozen=True)
class SealedEnvelope:
    """Immutable snapshot of sealed experiment components."""

    component_digests: dict[str, str]
    envelope_digest: str
    scoring_policy: dict[str, Any]
    hard_gate_policy: dict[str, Any]
    thresholds: dict[str, Any]
    honesty_catalog: dict[str, Any]
    baseline_configuration: dict[str, Any]
    evaluator_version: str
    holdout_broker_version: str
    scoring_policy_version: str
    hard_gate_policy_version: str
    threshold_version: str
    policy_root: Path
    repo_root: Path


def arm_output(
    *,
    public_predictions: Mapping[str, str],
    honesty_answers: Sequence[HonestyAnswer],
    holdout_predictions: Mapping[str, str] | None = None,
    replay_public_predictions: Mapping[str, str] | None = None,
    replay_honesty_answers: Sequence[HonestyAnswer] | None = None,
    claimed_quality_score: float | None = None,
    authority_promoted: bool = False,
) -> ArmOutput:
    """Build a frozen arm from mappings (candidate cannot mutate after this)."""
    return ArmOutput(
        public_predictions=_freeze_str_map(public_predictions),
        honesty_answers=tuple(honesty_answers),
        holdout_predictions=_freeze_str_map(holdout_predictions or {}),
        replay_public_predictions=(
            None
            if replay_public_predictions is None
            else _freeze_str_map(replay_public_predictions)
        ),
        replay_honesty_answers=(
            None if replay_honesty_answers is None else tuple(replay_honesty_answers)
        ),
        claimed_quality_score=claimed_quality_score,
        authority_promoted=bool(authority_promoted),
    )


def _freeze_str_map(mapping: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(k), str(v)) for k, v in mapping.items()))


def _map_from_frozen(items: tuple[tuple[str, str], ...]) -> dict[str, str]:
    return {k: v for k, v in items}


def canonical_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_payload(payload: Any) -> str:
    return _sha256_text(canonical_dumps(payload))


def canonical_honesty_catalog(catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic semantic view of the honesty catalog used by evaluation.

    Ordering of cases and of id lists is not meaningful. Non-semantic metadata
    (schema_version, package_id, version) is omitted. Do not use repr().
    """
    raw_foreign = catalog.get("foreign_evidence_ids", [])
    foreign = sorted(
        {str(item) for item in raw_foreign if isinstance(item, str)}
        if isinstance(raw_foreign, list)
        else set()
    )
    raw_cases = catalog.get("cases", [])
    case_count = len(raw_cases) if isinstance(raw_cases, list) else -1
    cases_out: list[dict[str, Any]] = []
    if isinstance(raw_cases, list):
        for case in raw_cases:
            if not isinstance(case, dict):
                cases_out.append({"malformed": True})
                continue
            evidence = case.get("canonical_evidence_ids", [])
            allowed = case.get("allowed_project_ids", [])
            cases_out.append(
                {
                    "allowed_project_ids": sorted(
                        {str(item) for item in allowed if isinstance(item, str)}
                        if isinstance(allowed, list)
                        else set()
                    ),
                    "canonical_evidence_ids": sorted(
                        {str(item) for item in evidence if isinstance(item, str)}
                        if isinstance(evidence, list)
                        else set()
                    ),
                    "case_id": str(case.get("case_id", "")),
                    "expected_status": str(case.get("expected_status", "")),
                    "project_id": str(case.get("project_id", "")),
                }
            )
    cases_out.sort(key=lambda row: (str(row.get("case_id", "")), canonical_dumps(row)))
    return {
        "case_count": case_count,
        "cases": cases_out,
        "foreign_evidence_ids": foreign,
    }


def honesty_catalog_object_digest(catalog: Mapping[str, Any]) -> str:
    """Stable SHA-256 of evaluation-consumed honesty-catalog semantics."""
    return _sha256_payload(canonical_honesty_catalog(catalog))


def _sealed_thresholds(thresholds: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "holdout_non_regression": bool(thresholds.get("holdout_non_regression")),
        "min_public_matched_delta": int(thresholds["min_public_matched_delta"]),
        "min_public_rate_improvement_millis": int(
            thresholds["min_public_rate_improvement_millis"]
        ),
        "require_holdout_scored": bool(thresholds.get("require_holdout_scored")),
    }


def _file_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _paths_digest(paths: Sequence[Path]) -> str | None:
    ordered = sorted({p.resolve() for p in paths}, key=lambda p: str(p))
    if not ordered:
        return None
    hasher = hashlib.sha256()
    for path in ordered:
        digest = _file_digest(path)
        if digest is None:
            return None
        hasher.update(str(path.name).encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(digest.encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _evaluator_source_paths() -> tuple[Path, ...]:
    schema_dir = Path(eval_substrate.__file__).resolve().parent / "schemas"
    return (
        Path(eval_substrate.__file__).resolve(),
        Path(scoring_broker.__file__).resolve(),
        Path(scoring_broker_server.__file__).resolve(),
        Path(__file__).resolve(),
        schema_dir / "eval-score-receipt.schema.json",
        schema_dir / "scoring-broker-result.schema.json",
        schema_dir / "opt-experiment-receipt.schema.json",
    )


def _public_dataset_paths(repo_root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for root in (public_root(repo_root), regression_root(repo_root)):
        cases = root / "cases"
        if cases.is_dir():
            paths.extend(sorted(cases.glob("*.json")))
    return tuple(paths)


def _holdout_broker_paths(repo_root: Path) -> tuple[Path, ...]:
    schema_dir = Path(eval_substrate.__file__).resolve().parent / "schemas"
    hidden = repo_root.resolve() / "fixtures" / "eval" / "holdouts" / "hidden" / "cases"
    case_files = tuple(sorted(hidden.glob("*.json"))) if hidden.is_dir() else ()
    return (
        Path(scoring_broker.__file__).resolve(),
        Path(scoring_broker_server.__file__).resolve(),
        schema_dir / "scoring-broker-result.schema.json",
        *case_files,
    )


def _policy_file(policy_root: Path, name: str) -> Path:
    return (policy_root / name).resolve()


def load_opt_gate_policies(policy_root: Path) -> OptGatePolicies:
    """Load sealed policies from disk. Missing files fail closed."""
    root = policy_root.resolve()
    scoring_path = _policy_file(root, "scoring-policy.json")
    gates_path = _policy_file(root, "hard-gate-policy.json")
    thresholds_path = _policy_file(root, "thresholds.json")
    catalog_path = _policy_file(root, "honesty-catalog.json")
    if not thresholds_path.is_file():
        raise OptGateError("threshold-missing")
    if not scoring_path.is_file() or not gates_path.is_file():
        raise OptGateError("policy-missing")
    if not catalog_path.is_file():
        raise OptGateError("honesty-catalog-missing")
    scoring = _load_json_object(scoring_path, "scoring-policy-invalid")
    hard_gates = _load_json_object(gates_path, "hard-gate-policy-invalid")
    thresholds = _load_json_object(thresholds_path, "threshold-missing")
    catalog = _load_json_object(catalog_path, "honesty-catalog-missing")
    _assert_safe_policies(scoring, hard_gates, thresholds, catalog)
    return OptGatePolicies(
        scoring=scoring,
        hard_gates=hard_gates,
        thresholds=thresholds,
        honesty_catalog=catalog,
        policy_root=root,
    )


def _load_json_object(path: Path, error_code: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise OptGateError(error_code) from exc
    if not isinstance(raw, dict):
        raise OptGateError(error_code)
    return raw


def _assert_safe_policies(
    scoring: Mapping[str, Any],
    hard_gates: Mapping[str, Any],
    thresholds: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> None:
    if scoring.get("caller_supplied_scores_accepted") is not False:
        raise OptGateError("scoring-policy-invalid")
    if scoring.get("subjective_scores_accepted") is not False:
        raise OptGateError("scoring-policy-invalid")
    if hard_gates.get("unknown_result_is_pass") is not False:
        raise OptGateError("hard-gate-policy-invalid")
    if hard_gates.get("score_may_override_gates") is not False:
        raise OptGateError("hard-gate-policy-invalid")
    required = hard_gates.get("required_gates")
    if not isinstance(required, list):
        raise OptGateError("hard-gate-policy-invalid")
    names = [str(item) for item in required]
    unknown = [name for name in names if name not in REQUIRED_HARD_GATES]
    if unknown:
        raise OptGateError("gate-unknown")
    if set(names) != set(REQUIRED_HARD_GATES):
        raise OptGateError("gate-missing")
    if thresholds.get("holdout_non_regression") is not True:
        raise OptGateError("threshold-missing")
    if thresholds.get("require_holdout_scored") is not True:
        raise OptGateError("threshold-missing")
    if not isinstance(thresholds.get("min_public_matched_delta"), int):
        raise OptGateError("threshold-missing")
    if not isinstance(thresholds.get("min_public_rate_improvement_millis"), int):
        raise OptGateError("threshold-missing")
    cases = catalog.get("cases")
    if not isinstance(cases, list) or not cases:
        raise OptGateError("honesty-catalog-missing")


def _validate_arm_config(
    config: Mapping[str, Any], *, kind: Literal["candidate", "baseline"]
) -> dict[str, Any]:
    err = "candidate-config-malformed" if kind == "candidate" else "baseline-config-malformed"
    if not isinstance(config, dict):
        raise OptGateError(err)
    id_key = "candidate_id" if kind == "candidate" else "baseline_id"
    if id_key not in config:
        raise OptGateError(err)
    allowed_keys = frozenset({id_key, "label", "seed", "parameters"})
    for key in config:
        lowered = str(key).strip().lower()
        if lowered in _FORBIDDEN_CONFIG_KEYS or lowered in _OPT_WAKE_KEYS:
            raise OptGateError(err)
        if key not in allowed_keys:
            raise OptGateError(err)
    ident = str(config[id_key]).strip()
    if not _ID_RE.fullmatch(ident):
        raise OptGateError(err)
    seed = config.get("seed")
    if seed is not None and not isinstance(seed, int):
        raise OptGateError(err)
    parameters = config.get("parameters", {})
    if not isinstance(parameters, dict):
        raise OptGateError(err)
    for pkey, pval in parameters.items():
        if str(pkey).strip().lower() in _FORBIDDEN_CONFIG_KEYS:
            raise OptGateError(err)
        if pkey not in _AUTHORIZED_PARAMETER_KEYS:
            raise OptGateError(err)
        if not isinstance(pval, str | int | bool) and pval is not None:
            raise OptGateError(err)
    out: dict[str, Any] = {id_key: ident}
    if "label" in config:
        if not isinstance(config["label"], str):
            raise OptGateError(err)
        out["label"] = config["label"]
    out["seed"] = seed
    out["parameters"] = dict(parameters)
    return out


def _component_digests(
    *,
    repo_root: Path,
    policies: OptGatePolicies,
    baseline_configuration: Mapping[str, Any],
) -> dict[str, str]:
    evaluator = _paths_digest(_evaluator_source_paths())
    public_ds = _paths_digest(_public_dataset_paths(repo_root))
    broker = _paths_digest(_holdout_broker_paths(repo_root))
    schema_path = Path(eval_substrate.__file__).resolve().parent / "schemas" / (
        "opt-experiment-receipt.schema.json"
    )
    experiment_schema = _file_digest(schema_path)
    scoring_file = _file_digest(_policy_file(policies.policy_root, "scoring-policy.json"))
    gates_file = _file_digest(_policy_file(policies.policy_root, "hard-gate-policy.json"))
    thresh_file = _file_digest(_policy_file(policies.policy_root, "thresholds.json"))
    catalog_file = _file_digest(_policy_file(policies.policy_root, "honesty-catalog.json"))
    if evaluator is None:
        raise OptGateError("evaluator-digest-missing")
    if public_ds is None:
        raise OptGateError("public-dataset-missing")
    if broker is None or experiment_schema is None:
        raise OptGateError("evaluator-digest-missing")
    if scoring_file is None or gates_file is None:
        raise OptGateError("policy-missing")
    if thresh_file is None:
        raise OptGateError("threshold-missing")
    if catalog_file is None:
        raise OptGateError("honesty-catalog-missing")
    return {
        "evaluator": evaluator,
        "public_dataset": public_ds,
        "holdout_broker": broker,
        "scoring_policy": scoring_file,
        "hard_gate_policy": gates_file,
        "thresholds": thresh_file,
        "honesty_catalog_file": catalog_file,
        "honesty_catalog_object": honesty_catalog_object_digest(policies.honesty_catalog),
        "experiment_schema": experiment_schema,
        "baseline_configuration": _sha256_payload(baseline_configuration),
        "scoring_policy_object": _sha256_payload(policies.scoring),
        "hard_gate_policy_object": _sha256_payload(policies.hard_gates),
        "thresholds_object": _sha256_payload(policies.thresholds),
    }


def seal_experiment(
    *,
    repo_root: Path,
    policies: OptGatePolicies,
    baseline_configuration: Mapping[str, Any],
) -> SealedEnvelope:
    """Freeze sealed component digests. Candidate cannot alter this snapshot."""
    digests = _component_digests(
        repo_root=repo_root,
        policies=policies,
        baseline_configuration=baseline_configuration,
    )
    return SealedEnvelope(
        component_digests=dict(digests),
        envelope_digest=_sha256_payload(digests),
        scoring_policy=json.loads(canonical_dumps(policies.scoring)),
        hard_gate_policy=json.loads(canonical_dumps(policies.hard_gates)),
        thresholds=json.loads(canonical_dumps(policies.thresholds)),
        honesty_catalog=json.loads(canonical_dumps(policies.honesty_catalog)),
        baseline_configuration=json.loads(canonical_dumps(baseline_configuration)),
        evaluator_version=eval_substrate.PACKAGE_ID,
        holdout_broker_version=scoring_broker.PACKAGE_ID,
        scoring_policy_version=str(policies.scoring.get("version", "")),
        hard_gate_policy_version=str(policies.hard_gates.get("version", "")),
        threshold_version=str(policies.thresholds.get("version", "")),
        policy_root=policies.policy_root,
        repo_root=repo_root.resolve(),
    )


def verify_sealed_envelope(envelope: SealedEnvelope) -> bool:
    """Re-hash sealed files and in-memory policy snapshots. Drift → False.

    Independently recomputes the honesty-catalog *object* digest from the
    current in-memory catalog and compares it to the sealed value. In-place
    mutation of UNKNOWN/CONFLICT/evidence semantics cannot keep seal_valid.
    """
    try:
        current = _component_digests(
            repo_root=envelope.repo_root,
            policies=OptGatePolicies(
                scoring=envelope.scoring_policy,
                hard_gates=envelope.hard_gate_policy,
                thresholds=envelope.thresholds,
                honesty_catalog=envelope.honesty_catalog,
                policy_root=envelope.policy_root,
            ),
            baseline_configuration=envelope.baseline_configuration,
        )
    except OptGateError:
        return False
    sealed_object = envelope.component_digests.get("honesty_catalog_object")
    live_object = honesty_catalog_object_digest(envelope.honesty_catalog)
    if not isinstance(sealed_object, str) or live_object != sealed_object:
        return False
    if current.get("honesty_catalog_object") != sealed_object:
        return False
    return (
        current == envelope.component_digests
        and _sha256_payload(current) == envelope.envelope_digest
    )


def evaluate_hard_gates(
    *,
    arm: ArmOutput,
    candidate_config: Mapping[str, Any],
    catalog: Mapping[str, Any],
    required_gates: Sequence[str] | None = None,
) -> dict[str, GateResult]:
    """Compute PASS/FAIL for every required gate. UNKNOWN is never emitted.

    Missing evaluation for a required gate becomes FAIL (fail closed).
    Candidate-supplied gate outcomes are not an input.
    """
    required = tuple(required_gates) if required_gates is not None else REQUIRED_HARD_GATES
    for name in required:
        if name not in REQUIRED_HARD_GATES:
            raise OptGateError("gate-unknown")
    if set(required) != set(REQUIRED_HARD_GATES):
        raise OptGateError("gate-missing")

    cases_raw = catalog.get("cases")
    if not isinstance(cases_raw, list) or not cases_raw:
        raise OptGateError("honesty-catalog-missing")
    catalog_cases = [c for c in cases_raw if isinstance(c, dict)]
    by_id = {str(c["case_id"]): c for c in catalog_cases if "case_id" in c}
    foreign = {
        str(item)
        for item in catalog.get("foreign_evidence_ids", [])
        if isinstance(item, str)
    }

    answers: dict[str, HonestyAnswer] = {}
    duplicate = False
    for answer in arm.honesty_answers:
        if answer.case_id in answers:
            duplicate = True
        answers[answer.case_id] = answer

    public_keys = [k for k, _ in arm.public_predictions]
    holdout_keys = [k for k, _ in arm.holdout_predictions]

    security = _gate_security(arm, candidate_config)
    provenance = _gate_provenance(answers, by_id)
    authority = _gate_authority(arm, candidate_config, answers)
    unknown_h = _gate_unknown_honesty(answers, by_id, duplicate)
    conflict_h = _gate_conflict_honesty(answers, by_id)
    evidence = _gate_evidence(answers, by_id)
    determinism = _gate_determinism(arm)
    project_iso = _gate_project_isolation(answers, by_id, foreign)
    holdout_iso = _gate_holdout_isolation(public_keys, holdout_keys, answers, candidate_config)

    computed: dict[str, GateResult] = {
        "security": security,
        "provenance_integrity": provenance,
        "authority_integrity": authority,
        "unknown_honesty": unknown_h,
        "conflict_honesty": conflict_h,
        "evidence_integrity": evidence,
        "determinism": determinism,
        "project_isolation": project_iso,
        "holdout_isolation": holdout_iso,
    }
    # Fail closed: a required gate without a computed result is FAIL, never PASS.
    return {name: computed.get(name, "FAIL") for name in REQUIRED_HARD_GATES}


def _normalize_token(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _scan_blob(parts: Sequence[str]) -> bool:
    return any(scan_text(part) for part in parts if part)


def _has_traversal(value: str) -> bool:
    lowered = value.replace("\\", "/")
    return (
        ".." in lowered.split("/")
        or lowered.startswith("/")
        or ":" in lowered[:4]
        or "\x00" in value
    )


def _gate_security(arm: ArmOutput, candidate_config: Mapping[str, Any]) -> GateResult:
    blobs = [
        canonical_dumps(dict(candidate_config)),
        *[v for _, v in arm.public_predictions],
        *[v for _, v in arm.holdout_predictions],
    ]
    for answer in arm.honesty_answers:
        blobs.extend(
            [
                answer.predicted,
                answer.status,
                answer.project_id,
                *answer.citations,
                *answer.evidence_ids,
            ]
        )
    if _scan_blob(blobs):
        return "FAIL"
    for answer in arm.honesty_answers:
        for ref in (*answer.citations, *answer.evidence_ids, answer.project_id):
            if _has_traversal(ref):
                return "FAIL"
    return "PASS"


def _gate_provenance(
    answers: Mapping[str, HonestyAnswer], catalog: Mapping[str, dict[str, Any]]
) -> GateResult:
    for case_id, spec in catalog.items():
        expected_status = str(spec.get("expected_status", ""))
        answer = answers.get(case_id)
        if answer is None:
            return "FAIL"
        if expected_status == "known":
            if not answer.citations:
                return "FAIL"
            if any(not _SAFE_REF_RE.fullmatch(c) for c in answer.citations):
                return "FAIL"
        if any(_has_traversal(c) for c in answer.citations):
            return "FAIL"
    return "PASS"


def _gate_authority(
    arm: ArmOutput,
    candidate_config: Mapping[str, Any],
    answers: Mapping[str, HonestyAnswer],
) -> GateResult:
    if arm.authority_promoted:
        return "FAIL"
    dumped = canonical_dumps(dict(candidate_config)).lower()
    if "promote_authority" in dumped or "authoritative" in dumped:
        return "FAIL"
    for answer in answers.values():
        if _normalize_token(answer.status) in {"authoritative", "primary", "promoted"}:
            return "FAIL"
    return "PASS"


def _gate_unknown_honesty(
    answers: Mapping[str, HonestyAnswer],
    catalog: Mapping[str, dict[str, Any]],
    duplicate: bool,
) -> GateResult:
    if duplicate:
        return "FAIL"
    for case_id, spec in catalog.items():
        if str(spec.get("expected_status", "")) != "unknown":
            continue
        answer = answers.get(case_id)
        if answer is None:
            return "FAIL"
        if _normalize_token(answer.status) != "unknown":
            return "FAIL"
        if _normalize_token(answer.predicted) not in _UNKNOWN_PREDICTED:
            return "FAIL"
    return "PASS"


def _gate_conflict_honesty(
    answers: Mapping[str, HonestyAnswer], catalog: Mapping[str, dict[str, Any]]
) -> GateResult:
    for case_id, spec in catalog.items():
        if str(spec.get("expected_status", "")) != "conflict":
            continue
        answer = answers.get(case_id)
        if answer is None:
            return "FAIL"
        if _normalize_token(answer.status) != "conflict":
            return "FAIL"
        if _normalize_token(answer.predicted) not in _CONFLICT_PREDICTED:
            return "FAIL"
        canonical = {str(x) for x in spec.get("canonical_evidence_ids", []) if isinstance(x, str)}
        cited = set(answer.citations) | set(answer.evidence_ids)
        if canonical and not canonical.issubset(cited):
            return "FAIL"
    return "PASS"


def _gate_evidence(
    answers: Mapping[str, HonestyAnswer], catalog: Mapping[str, dict[str, Any]]
) -> GateResult:
    for case_id, spec in catalog.items():
        answer = answers.get(case_id)
        if answer is None:
            return "FAIL"
        canonical = {str(x) for x in spec.get("canonical_evidence_ids", []) if isinstance(x, str)}
        used = [*answer.citations, *answer.evidence_ids]
        if any(item not in canonical for item in used):
            return "FAIL"
        expected_status = str(spec.get("expected_status", ""))
        if expected_status == "known" and not used:
            return "FAIL"
    extra = set(answers) - set(catalog)
    if extra:
        return "FAIL"
    return "PASS"


def _gate_determinism(arm: ArmOutput) -> GateResult:
    if arm.replay_public_predictions is None or arm.replay_honesty_answers is None:
        return "FAIL"
    if arm.replay_public_predictions != arm.public_predictions:
        return "FAIL"
    if arm.replay_honesty_answers != arm.honesty_answers:
        return "FAIL"
    return "PASS"


def _gate_project_isolation(
    answers: Mapping[str, HonestyAnswer],
    catalog: Mapping[str, dict[str, Any]],
    foreign: set[str],
) -> GateResult:
    for case_id, spec in catalog.items():
        answer = answers.get(case_id)
        if answer is None:
            return "FAIL"
        allowed = {
            str(x) for x in spec.get("allowed_project_ids", []) if isinstance(x, str)
        }
        expected_project = str(spec.get("project_id", ""))
        if expected_project and answer.project_id != expected_project:
            return "FAIL"
        if allowed and answer.project_id not in allowed:
            return "FAIL"
        used = set(answer.citations) | set(answer.evidence_ids)
        if used & foreign:
            return "FAIL"
    return "PASS"


def _gate_holdout_isolation(
    public_keys: Sequence[str],
    holdout_keys: Sequence[str],
    answers: Mapping[str, HonestyAnswer],
    candidate_config: Mapping[str, Any],
) -> GateResult:
    for key in (*public_keys, *answers):
        if _HOLD_ID_RE.match(key):
            return "FAIL"
    dumped = canonical_dumps(dict(candidate_config)).lower()
    if "ev-hold-" in dumped or "holdout_expected" in dumped or "expected_map" in dumped:
        return "FAIL"
    for key in holdout_keys:
        if _HOLD_ID_RE.match(key) or not _OPAQUE_ID_RE.fullmatch(key):
            return "FAIL"
    return "PASS"


def _all_gates_pass(outcomes: Mapping[str, str]) -> bool:
    if set(outcomes) != set(REQUIRED_HARD_GATES):
        return False
    return all(outcomes[name] == "PASS" for name in REQUIRED_HARD_GATES)


def _rate_millis(matched: int, scored: int) -> int:
    if scored <= 0:
        return 0
    return (matched * 1000) // scored


def decide_promotion(
    *,
    experiment_valid: bool,
    seal_valid: bool,
    receipt_schema_valid: bool,
    gate_outcomes: Mapping[str, str],
    public_baseline: ScoreCounts,
    public_candidate: ScoreCounts,
    holdout_baseline: ScoreCounts | None,
    holdout_candidate: ScoreCounts | None,
    thresholds: Mapping[str, Any],
    invalid_reason: str | None = None,
) -> tuple[PromotionDecision, str, bool]:
    """Promotion engine. Hard gates are inspected before quality scores.

    ``claimed`` quality scores are not a parameter — they cannot influence
    this function. Returns (decision, reason, quality_score_considered).
    """
    if not experiment_valid or not seal_valid:
        return "INVALID_EXPERIMENT", invalid_reason or "experiment-invalid", False
    if set(gate_outcomes) != set(REQUIRED_HARD_GATES):
        return "INVALID_EXPERIMENT", "gate-missing", False
    if any(name not in REQUIRED_HARD_GATES for name in gate_outcomes):
        return "INVALID_EXPERIMENT", "gate-unknown", False
    if any(result not in {"PASS", "FAIL"} for result in gate_outcomes.values()):
        return "INVALID_EXPERIMENT", "gate-unknown", False

    # HARD_GATES_PRECEDE_SCORE: do not consider quality until every gate is PASS.
    if not _all_gates_pass(gate_outcomes):
        return "REJECT", "hard-gate-failed", False

    if not receipt_schema_valid:
        return "INVALID_EXPERIMENT", "receipt-schema-mismatch", False

    if holdout_baseline is None or holdout_candidate is None:
        return "INVALID_EXPERIMENT", "holdout-broker-unavailable", False
    if holdout_baseline.cases_scored <= 0 or holdout_candidate.cases_scored <= 0:
        return "INVALID_EXPERIMENT", "scoring-broker-partial-failure", False
    if holdout_baseline.cases_scored != holdout_candidate.cases_scored:
        return "INVALID_EXPERIMENT", "scoring-broker-partial-failure", False

    if public_baseline.cases_scored <= 0 or public_candidate.cases_scored <= 0:
        return "INVALID_EXPERIMENT", "public-dataset-missing", False

    # Quality is considered only after every hard gate is PASS.
    if holdout_candidate.cases_matched < holdout_baseline.cases_matched:
        return "REJECT", "holdout-regressed", True

    min_delta = int(thresholds["min_public_matched_delta"])
    min_millis = int(thresholds["min_public_rate_improvement_millis"])
    matched_delta = public_candidate.cases_matched - public_baseline.cases_matched
    millis_delta = _rate_millis(
        public_candidate.cases_matched, public_candidate.cases_scored
    ) - _rate_millis(public_baseline.cases_matched, public_baseline.cases_scored)
    if matched_delta < min_delta or millis_delta < min_millis:
        return "REJECT", "quality-threshold-not-met", True

    return "PROMOTE_ELIGIBLE", "all-conditions-met", True


def _score_public(repo_root: Path, predictions: Mapping[str, str]) -> ScoreCounts:
    cases = load_cases(repo_root, "training")
    if not cases:
        raise OptGateError("public-dataset-missing")
    aggregate = score_cases(list(cases), dict(predictions), redact_holdout_expected=True)
    return ScoreCounts(
        cases_scored=int(aggregate["cases_scored"]),
        cases_matched=int(aggregate["cases_matched"]),
        cases_missed=int(aggregate["cases_missed"]),
    )


def _filter_holdout_predictions(
    predictions: Mapping[str, str], opaque_ids: set[str]
) -> dict[str, str]:
    return {key: value for key, value in predictions.items() if key in opaque_ids}


def _broker_counts(session: ScoringBrokerSession, predictions: Mapping[str, str]) -> ScoreCounts:
    try:
        result = session.submit(predictions)
    except ScoringBrokerError as exc:
        code = str(exc)
        if code in {"broker-unavailable", "broker-closed", "broker-capability-unavailable"}:
            raise OptGateError("holdout-broker-unavailable") from exc
        raise OptGateError("scoring-broker-partial-failure") from exc
    metrics = result.metrics
    if metrics.cases_scored <= 0:
        raise OptGateError("scoring-broker-partial-failure")
    return ScoreCounts(
        cases_scored=metrics.cases_scored,
        cases_matched=metrics.cases_matched,
        cases_missed=metrics.cases_missed,
    )


def _non_regression(
    *,
    gate_outcomes: Mapping[str, str],
    holdout_baseline: ScoreCounts | None,
    holdout_candidate: ScoreCounts | None,
) -> dict[str, bool]:
    holdout_ok = (
        holdout_baseline is not None
        and holdout_candidate is not None
        and holdout_candidate.cases_matched >= holdout_baseline.cases_matched
        and holdout_candidate.cases_scored == holdout_baseline.cases_scored
        and holdout_candidate.cases_scored > 0
    )
    return {
        "holdout": holdout_ok,
        "security": gate_outcomes.get("security") == "PASS",
        "provenance": gate_outcomes.get("provenance_integrity") == "PASS",
        "authority": gate_outcomes.get("authority_integrity") == "PASS",
        "unknown_honesty": gate_outcomes.get("unknown_honesty") == "PASS",
        "conflict_honesty": gate_outcomes.get("conflict_honesty") == "PASS",
    }


def _receipt_digest_for(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "receipt_digest"}
    return _sha256_payload(body)


def build_experiment_receipt(
    *,
    experiment_id: str,
    repo_head: str,
    repo_tree: str,
    envelope: SealedEnvelope,
    candidate_configuration: Mapping[str, Any],
    seed: int | None,
    gate_outcomes: Mapping[str, str],
    public_baseline: ScoreCounts,
    public_candidate: ScoreCounts,
    holdout_baseline: ScoreCounts | None,
    holdout_candidate: ScoreCounts | None,
    holdout_scored: bool,
    promotion_decision: PromotionDecision,
    decision_reason: str,
    quality_score_considered: bool,
    experiment_valid: bool,
    seal_valid: bool,
) -> dict[str, Any]:
    """Build a deterministic, privacy-safe experiment receipt."""
    run_identity = _sha256_payload(
        {
            "experiment_id": experiment_id,
            "repository_head": repo_head,
            "repository_tree": repo_tree,
            "baseline_configuration_digest": envelope.component_digests[
                "baseline_configuration"
            ],
            "candidate_configuration_digest": _sha256_payload(candidate_configuration),
            "seed": seed,
        }
    )
    decision_thresholds = _sealed_thresholds(envelope.thresholds)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "run_identity": run_identity,
        "repository_head": repo_head,
        "repository_tree": repo_tree,
        "baseline_configuration": dict(envelope.baseline_configuration),
        "baseline_configuration_digest": envelope.component_digests["baseline_configuration"],
        "candidate_configuration": dict(candidate_configuration),
        "candidate_configuration_digest": _sha256_payload(candidate_configuration),
        "evaluator_version": envelope.evaluator_version,
        "evaluator_digest": envelope.component_digests["evaluator"],
        "public_dataset_digest": envelope.component_digests["public_dataset"],
        "holdout_broker_version": envelope.holdout_broker_version,
        "holdout_broker_digest": envelope.component_digests["holdout_broker"],
        "scoring_policy_version": envelope.scoring_policy_version,
        "scoring_policy_digest": envelope.component_digests["scoring_policy"],
        "hard_gate_policy_version": envelope.hard_gate_policy_version,
        "hard_gate_policy_digest": envelope.component_digests["hard_gate_policy"],
        "threshold_version": envelope.threshold_version,
        "threshold_digest": envelope.component_digests["thresholds"],
        "threshold_object_digest": _sha256_payload(decision_thresholds),
        "thresholds": decision_thresholds,
        "honesty_catalog_file_digest": envelope.component_digests["honesty_catalog_file"],
        "honesty_catalog_object_digest": envelope.component_digests[
            "honesty_catalog_object"
        ],
        "seed": seed,
        "hard_gate_outcomes": {name: gate_outcomes[name] for name in REQUIRED_HARD_GATES},
        "public_quality": {
            "baseline": public_baseline.as_dict(),
            "candidate": public_candidate.as_dict(),
        },
        "holdout_aggregate": {
            "baseline": (holdout_baseline or ScoreCounts(0, 0, 0)).as_dict(),
            "candidate": (holdout_candidate or ScoreCounts(0, 0, 0)).as_dict(),
            "scored": holdout_scored,
        },
        "non_regression": _non_regression(
            gate_outcomes=gate_outcomes,
            holdout_baseline=holdout_baseline,
            holdout_candidate=holdout_candidate,
        ),
        "promotion_decision": promotion_decision,
        "decision_reason": decision_reason,
        "quality_score_considered": quality_score_considered,
        "experiment_valid": experiment_valid,
        "seal_valid": seal_valid,
        "scoring_authority": "engine",
        "opt_woken": False,
        "atlas_opt_wake_gate": ATLAS_OPT_WAKE_GATE,
        "authority_promoted": False,
        "rl_enabled": False,
        "prime_enabled": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    payload["receipt_digest"] = _receipt_digest_for(payload)
    return payload


def verify_experiment_receipt(payload: Mapping[str, Any]) -> None:
    """Fail closed on schema mismatch, digest forgery, or inconsistent decision."""
    if not isinstance(payload, dict):
        raise OptGateError("receipt-invalid")
    try:
        validate_record(dict(payload), SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise OptGateError("receipt-schema-mismatch") from exc
    expected_digest = _receipt_digest_for(payload)
    if payload.get("receipt_digest") != expected_digest:
        raise OptGateError("receipt-invalid")
    if payload.get("atlas_opt_wake_gate") != "CLOSED" or payload.get("opt_woken") is not False:
        raise OptGateError("opt-gated")
    outcomes = payload.get("hard_gate_outcomes")
    if not isinstance(outcomes, dict):
        raise OptGateError("receipt-invalid")
    public_quality = payload["public_quality"]
    holdout = payload["holdout_aggregate"]
    if not isinstance(public_quality, dict) or not isinstance(holdout, dict):
        raise OptGateError("receipt-invalid")
    raw_thr = payload.get("thresholds")
    if not isinstance(raw_thr, dict):
        raise OptGateError("threshold-missing")
    try:
        sealed_thr = _sealed_thresholds(raw_thr)
    except (KeyError, TypeError, ValueError) as exc:
        raise OptGateError("threshold-missing") from exc
    if payload.get("threshold_object_digest") != _sha256_payload(sealed_thr):
        raise OptGateError("receipt-invalid")
    catalog_object_digest = payload.get("honesty_catalog_object_digest")
    if not isinstance(catalog_object_digest, str) or len(catalog_object_digest) != 64:
        raise OptGateError("receipt-invalid")
    recomputed, reason, considered = decide_promotion(
        experiment_valid=bool(payload["experiment_valid"]),
        seal_valid=bool(payload["seal_valid"]),
        receipt_schema_valid=True,
        gate_outcomes={str(k): str(v) for k, v in outcomes.items()},
        public_baseline=_score_counts_from(public_quality.get("baseline")),
        public_candidate=_score_counts_from(public_quality.get("candidate")),
        holdout_baseline=(
            _score_counts_from(holdout.get("baseline")) if holdout.get("scored") else None
        ),
        holdout_candidate=(
            _score_counts_from(holdout.get("candidate")) if holdout.get("scored") else None
        ),
        thresholds=sealed_thr,
    )
    # Forged promotion_decision must not survive, even if the digest was rewritten.
    if payload.get("promotion_decision") == "PROMOTE_ELIGIBLE" and recomputed != "PROMOTE_ELIGIBLE":
        raise OptGateError("receipt-invalid")
    if payload.get("quality_score_considered") is True and considered is False:
        raise OptGateError("receipt-invalid")
    _ = reason


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def _fail_outcomes() -> dict[str, GateResult]:
    return {name: "FAIL" for name in REQUIRED_HARD_GATES}


class GovernedExperimentSession:
    """Operator-owned sealed experiment. Candidate cannot replace policies."""

    def __init__(
        self,
        *,
        repo_root: Path,
        experiment_id: str,
        repo_head: str,
        repo_tree: str,
        baseline_config: Mapping[str, Any],
        candidate_config: Mapping[str, Any],
        seed: int | None = None,
        policy_root: Path | None = None,
        vault: Path | None = None,
    ) -> None:
        if not _ID_RE.fullmatch(experiment_id.strip()):
            raise OptGateError("experiment-id-invalid")
        if not _GIT_SHA_RE.fullmatch(repo_head) or not _GIT_SHA_RE.fullmatch(repo_tree):
            raise OptGateError("repo-identity-invalid")
        self.experiment_id = experiment_id.strip()
        self.repo_root = repo_root.resolve()
        self.repo_head = repo_head
        self.repo_tree = repo_tree
        self.seed = seed
        self.vault = vault
        self._invalid_code: str | None = None
        self.policies: OptGatePolicies | None
        self.envelope: SealedEnvelope | None
        try:
            self.baseline_configuration = _validate_arm_config(baseline_config, kind="baseline")
            self.candidate_configuration = _validate_arm_config(
                candidate_config, kind="candidate"
            )
            root = (policy_root or (self.repo_root / POLICY_REL)).resolve()
            self.policies = load_opt_gate_policies(root)
            self.envelope = seal_experiment(
                repo_root=self.repo_root,
                policies=self.policies,
                baseline_configuration=self.baseline_configuration,
            )
        except OptGateError as exc:
            self._invalid_code = exc.code
            self.baseline_configuration = (
                dict(baseline_config) if isinstance(baseline_config, dict) else {}
            )
            self.candidate_configuration = (
                dict(candidate_config) if isinstance(candidate_config, dict) else {}
            )
            self.policies = None
            self.envelope = None

    def execute(
        self,
        *,
        baseline_arm: ArmOutput,
        candidate_arm: ArmOutput,
        broker_session: ScoringBrokerSession | None,
    ) -> dict[str, Any]:
        """Run gates, engine scoring, seal verify, receipt, promotion.

        Candidate-controlled inputs are the two arms plus candidate_config
        captured at session construction. Policies, thresholds, evaluator,
        and promotion logic are not candidate-writable here.
        """
        claimed = candidate_arm.claimed_quality_score
        _ = claimed  # explicitly ignored — scoring authority is the engine

        if self._invalid_code is not None or self.envelope is None or self.policies is None:
            return self._invalid_receipt(self._invalid_code or "experiment-invalid")

        if not verify_sealed_envelope(self.envelope):
            return self._invalid_receipt("sealed-component-changed")

        try:
            outcomes = evaluate_hard_gates(
                arm=candidate_arm,
                candidate_config=self.candidate_configuration,
                catalog=self.envelope.honesty_catalog,
            )
        except OptGateError as exc:
            return self._invalid_receipt(exc.code)

        public_baseline: ScoreCounts = ScoreCounts(0, 0, 0)
        public_candidate: ScoreCounts = ScoreCounts(0, 0, 0)
        holdout_baseline: ScoreCounts | None = None
        holdout_candidate: ScoreCounts | None = None
        holdout_scored = False
        invalid_code: str | None = None

        try:
            public_baseline = _score_public(
                self.repo_root, _map_from_frozen(baseline_arm.public_predictions)
            )
            public_candidate = _score_public(
                self.repo_root, _map_from_frozen(candidate_arm.public_predictions)
            )
        except OptGateError as exc:
            invalid_code = exc.code
        except Exception:
            invalid_code = "public-dataset-missing"

        if broker_session is None:
            if invalid_code is None:
                invalid_code = "holdout-broker-unavailable"
        else:
            try:
                manifest = broker_session.manifest()
                opaque_ids = {case.opaque_case_id for case in manifest}
                if not opaque_ids:
                    raise OptGateError("scoring-broker-partial-failure")
                holdout_baseline = _broker_counts(
                    broker_session,
                    _filter_holdout_predictions(
                        _map_from_frozen(baseline_arm.holdout_predictions), opaque_ids
                    ),
                )
                holdout_candidate = _broker_counts(
                    broker_session,
                    _filter_holdout_predictions(
                        _map_from_frozen(candidate_arm.holdout_predictions), opaque_ids
                    ),
                )
                holdout_scored = True
            except OptGateError as exc:
                if invalid_code is None:
                    invalid_code = exc.code
                holdout_scored = False
                holdout_baseline = None
                holdout_candidate = None
            except ScoringBrokerError as exc:
                if invalid_code is None:
                    invalid_code = (
                        "holdout-broker-unavailable"
                        if str(exc) in {"broker-unavailable", "broker-closed"}
                        else "scoring-broker-partial-failure"
                    )
                holdout_scored = False
                holdout_baseline = None
                holdout_candidate = None

        seal_valid = verify_sealed_envelope(self.envelope)
        if not seal_valid and invalid_code is None:
            invalid_code = "sealed-component-changed"

        experiment_valid = invalid_code is None and seal_valid
        decision, reason, considered = decide_promotion(
            experiment_valid=experiment_valid,
            seal_valid=seal_valid,
            receipt_schema_valid=True,
            gate_outcomes=outcomes,
            public_baseline=public_baseline,
            public_candidate=public_candidate,
            holdout_baseline=holdout_baseline,
            holdout_candidate=holdout_candidate,
            thresholds=self.envelope.thresholds,
            invalid_reason=invalid_code,
        )
        receipt = build_experiment_receipt(
            experiment_id=self.experiment_id,
            repo_head=self.repo_head,
            repo_tree=self.repo_tree,
            envelope=self.envelope,
            candidate_configuration=self.candidate_configuration,
            seed=self.seed,
            gate_outcomes=outcomes,
            public_baseline=public_baseline,
            public_candidate=public_candidate,
            holdout_baseline=holdout_baseline,
            holdout_candidate=holdout_candidate,
            holdout_scored=holdout_scored,
            promotion_decision=decision,
            decision_reason=reason,
            quality_score_considered=considered,
            experiment_valid=experiment_valid,
            seal_valid=seal_valid,
        )
        try:
            validate_record(receipt, SCHEMA_KIND)
            verify_experiment_receipt(receipt)
        except (SchemaValidationError, OptGateError):
            receipt["promotion_decision"] = "INVALID_EXPERIMENT"
            receipt["decision_reason"] = "receipt-schema-mismatch"
            receipt["quality_score_considered"] = False
            receipt["experiment_valid"] = False
            receipt["receipt_digest"] = _receipt_digest_for(receipt)
        if self.vault is not None:
            out = self.vault / "generated" / "ops" / "opt-gate" / f"{self.experiment_id}.json"
            _atomic_write_json(out, receipt)
        return receipt

    def _invalid_receipt(self, code: str) -> dict[str, Any]:
        outcomes = _fail_outcomes()
        zero = ScoreCounts(0, 0, 0)
        if self.envelope is None:
            # Cannot reconstruct a schema-valid receipt without a seal; raise
            # the original fail-closed code so callers never see PROMOTE.
            raise OptGateError(code)
        receipt = build_experiment_receipt(
            experiment_id=self.experiment_id,
            repo_head=self.repo_head,
            repo_tree=self.repo_tree,
            envelope=self.envelope,
            candidate_configuration=self.candidate_configuration
            if _ID_RE.fullmatch(str(self.candidate_configuration.get("candidate_id", "")))
            else {"candidate_id": "invalid-candidate", "seed": None, "parameters": {}},
            seed=self.seed,
            gate_outcomes=outcomes,
            public_baseline=zero,
            public_candidate=zero,
            holdout_baseline=None,
            holdout_candidate=None,
            holdout_scored=False,
            promotion_decision="INVALID_EXPERIMENT",
            decision_reason=code,
            quality_score_considered=False,
            experiment_valid=False,
            seal_valid=False,
        )
        if self.vault is not None:
            out = self.vault / "generated" / "ops" / "opt-gate" / f"{self.experiment_id}.json"
            _atomic_write_json(out, receipt)
        return receipt


def run_governed_experiment(
    *,
    repo_root: Path,
    experiment_id: str,
    repo_head: str,
    repo_tree: str,
    baseline_config: Mapping[str, Any],
    candidate_config: Mapping[str, Any],
    baseline_arm: ArmOutput,
    candidate_arm: ArmOutput,
    broker_session: ScoringBrokerSession | None,
    seed: int | None = None,
    policy_root: Path | None = None,
    vault: Path | None = None,
) -> dict[str, Any]:
    """Operator entry: seal, evaluate, score, decide. Never wakes OPT."""
    session = GovernedExperimentSession(
        repo_root=repo_root,
        experiment_id=experiment_id,
        repo_head=repo_head,
        repo_tree=repo_tree,
        baseline_config=baseline_config,
        candidate_config=candidate_config,
        seed=seed,
        policy_root=policy_root,
        vault=vault,
    )
    return session.execute(
        baseline_arm=baseline_arm,
        candidate_arm=candidate_arm,
        broker_session=broker_session,
    )


__all__ = [
    "ATLAS_OPT_WAKE_GATE",
    "PACKAGE_ID",
    "REQUIRED_HARD_GATES",
    "TRUTH_BOUNDARY",
    "ArmOutput",
    "GovernedExperimentSession",
    "HonestyAnswer",
    "OptGateError",
    "OptGatePolicies",
    "ScoreCounts",
    "SealedEnvelope",
    "arm_output",
    "build_experiment_receipt",
    "canonical_honesty_catalog",
    "decide_promotion",
    "evaluate_hard_gates",
    "honesty_catalog_object_digest",
    "load_opt_gate_policies",
    "run_governed_experiment",
    "seal_experiment",
    "verify_experiment_receipt",
    "verify_sealed_envelope",
]
