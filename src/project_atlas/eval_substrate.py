"""AS-2.2-EVAL-001 — Eval substrate with hidden-holdout isolation.

P0 substrate only:
  - public fixtures + hidden holdouts
  - training/autolab path roles cannot resolve holdouts
  - deterministic objective scoring hooks (exact/prefix)

Gated / forbidden here:
  - ATLAS-OPT-001 / ATLAS-OPT-002 (OPT wakes later, vertical PASS only)
  - RL / Prime
  - subjective scores, authority promotion, invent-pilot claims
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.2-EVAL-001"
SCHEMA_KIND = "eval-score-receipt"
TRUTH_BOUNDARY = (
    "EVAL SUBSTRATE ≠ OPT / ≠ RL / ≠ PRIME / ≠ AUTHORITY / ≠ SUBJECTIVE SCORE"
)

PUBLIC_REL = Path("fixtures") / "eval" / "public"
HOLDOUT_REL = Path("fixtures") / "eval" / "holdouts" / "hidden"
CONFIG_REL = Path("fixtures") / "eval" / "configs"

EvalRole = Literal["training", "autolab", "scoring"]
ScoreMode = Literal["exact", "prefix"]

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_OPT_WAKE_KEYS = frozenset(
    {
        "wake_opt",
        "wake_atlas_opt",
        "enable_opt",
        "atlas_opt_001",
        "atlas_opt_002",
        "opt_001",
        "opt_002",
    }
)
_FORBIDDEN_CLAIM_KEYS = frozenset(
    {
        "rl",
        "prime",
        "invent_pilot",
        "authentic_pilot",
        "promote_authority",
        "subjective_score",
    }
)


class EvalSubstrateError(ValueError):
    """Fail-closed eval substrate error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def _refuse_opt_and_forbidden(**flags: Any) -> None:
    for key in _OPT_WAKE_KEYS:
        if bool(flags.get(key)):
            raise EvalSubstrateError("opt-gated:ATLAS-OPT-001/002-not-woken")
    for key in _FORBIDDEN_CLAIM_KEYS:
        if bool(flags.get(key)):
            raise EvalSubstrateError(f"forbidden-claim:{key}")


def repo_eval_root(repo_root: Path) -> Path:
    """Return fixtures/eval under a repository root (resolved)."""
    root = repo_root.resolve()
    return root / "fixtures" / "eval"


def holdout_root(repo_root: Path) -> Path:
    return (repo_root.resolve() / HOLDOUT_REL).resolve()


def public_root(repo_root: Path) -> Path:
    return (repo_root.resolve() / PUBLIC_REL).resolve()


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def allowed_case_roots(repo_root: Path, role: EvalRole) -> tuple[Path, ...]:
    """Path roots readable for a given role.

    training/autolab → public only.
    scoring → public + hidden holdouts.
    """
    pub = public_root(repo_root)
    if role in {"training", "autolab"}:
        return (pub,)
    if role == "scoring":
        return (pub, holdout_root(repo_root))
    raise EvalSubstrateError(f"role-unknown:{role}")


def assert_path_readable(repo_root: Path, role: EvalRole, path: Path) -> Path:
    """Fail closed if ``path`` is outside role-allowed eval roots."""
    resolved = path.resolve()
    allowed = allowed_case_roots(repo_root, role)
    if not any(is_under(resolved, root) for root in allowed):
        if is_under(resolved, holdout_root(repo_root)):
            raise EvalSubstrateError(f"holdout-isolated:{role}")
        raise EvalSubstrateError(f"path-outside-eval-roots:{role}")
    return resolved


def load_role_config(repo_root: Path, role: EvalRole) -> dict[str, Any]:
    """Load fixtures/eval/configs/{role}.paths.json and enforce isolation."""
    cfg_path = (repo_root.resolve() / CONFIG_REL / f"{role}.paths.json").resolve()
    if not cfg_path.is_file():
        raise EvalSubstrateError(f"config-missing:{role}")
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise EvalSubstrateError("config-invalid")
    roots_raw = raw.get("case_roots")
    if not isinstance(roots_raw, list) or not roots_raw:
        raise EvalSubstrateError("config-case-roots-missing")
    hold = holdout_root(repo_root)
    resolved_roots: list[Path] = []
    for item in roots_raw:
        if not isinstance(item, str):
            raise EvalSubstrateError("config-case-root-type")
        candidate = (repo_root.resolve() / item).resolve()
        if role in {"training", "autolab"} and is_under(candidate, hold):
            raise EvalSubstrateError(f"holdout-isolated:{role}-config")
        assert_path_readable(repo_root, role, candidate)
        resolved_roots.append(candidate)
    out = dict(raw)
    out["_resolved_case_roots"] = [str(p) for p in resolved_roots]
    return out


def list_case_files(repo_root: Path, role: EvalRole) -> list[Path]:
    """List *.json case files under role-allowed roots (deterministic order)."""
    files: list[Path] = []
    for root in allowed_case_roots(repo_root, role):
        cases_dir = root / "cases"
        if not cases_dir.is_dir():
            continue
        for path in sorted(cases_dir.glob("*.json")):
            assert_path_readable(repo_root, role, path)
            files.append(path)
    return files


def load_cases(repo_root: Path, role: EvalRole) -> list[dict[str, Any]]:
    """Load eval cases for role; holdouts remain invisible to training/autolab."""
    cases: list[dict[str, Any]] = []
    for path in list_case_files(repo_root, role):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise EvalSubstrateError(f"case-invalid:{path.name}")
        case_id = str(payload.get("case_id", "")).strip()
        if not case_id:
            raise EvalSubstrateError(f"case-id-missing:{path.name}")
        visibility = str(payload.get("visibility", "public")).strip()
        if visibility == "holdout" and role != "scoring":
            raise EvalSubstrateError(f"holdout-isolated:{role}")
        cases.append(payload)
    return cases


def _normalize_token(value: str) -> str:
    return " ".join(value.strip().lower().split())


def score_prediction(
    *,
    expected: str,
    predicted: str,
    mode: ScoreMode = "exact",
) -> dict[str, Any]:
    """Deterministic objective match — no subjective scores, no wall-clock."""
    exp = _normalize_token(expected)
    pred = _normalize_token(predicted)
    if mode == "exact":
        matched = exp == pred
    elif mode == "prefix":
        matched = bool(exp) and pred.startswith(exp)
    else:
        raise EvalSubstrateError(f"score-mode-unknown:{mode}")
    return {
        "mode": mode,
        "matched": matched,
        "expected_norm": exp,
        "predicted_norm": pred,
    }


def score_cases(
    cases: list[dict[str, Any]],
    predictions: dict[str, str],
) -> dict[str, Any]:
    """Score a prediction map against cases; deterministic aggregate counts."""
    results: list[dict[str, Any]] = []
    matched = 0
    for case in sorted(cases, key=lambda c: str(c.get("case_id", ""))):
        case_id = str(case["case_id"])
        mode = str(case.get("score_mode", "exact"))
        if mode not in {"exact", "prefix"}:
            raise EvalSubstrateError(f"score-mode-unknown:{mode}")
        expected = str(case.get("expected", ""))
        predicted = predictions.get(case_id, "")
        score_mode: ScoreMode = "prefix" if mode == "prefix" else "exact"
        one = score_prediction(
            expected=expected, predicted=predicted, mode=score_mode
        )
        row = {
            "case_id": case_id,
            "visibility": case.get("visibility", "public"),
            **one,
        }
        results.append(row)
        if one["matched"]:
            matched += 1
    total = len(results)
    return {
        "cases_scored": total,
        "cases_matched": matched,
        "cases_missed": total - matched,
        "results": results,
    }


def build_eval_score_receipt(
    vault: Path,
    *,
    record_id: str,
    repo_root: Path,
    predictions: dict[str, str],
    include_holdouts: bool = False,
    **flags: Any,
) -> dict[str, Any]:
    """Run scoring role, optionally include holdouts, write ops receipt."""
    _refuse_opt_and_forbidden(**flags)
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise EvalSubstrateError("eval-receipt-id-invalid")

    role: EvalRole = "scoring"
    # Always enforce config isolation for training/autolab side paths first.
    load_role_config(repo_root, "training")
    load_role_config(repo_root, "autolab")
    scoring_cfg = load_role_config(repo_root, "scoring")

    public_cases = load_cases(repo_root, "training")  # public-only view
    holdout_cases: list[dict[str, Any]] = []
    if include_holdouts:
        all_scoring = load_cases(repo_root, role)
        public_ids = {str(c["case_id"]) for c in public_cases}
        holdout_cases = [c for c in all_scoring if str(c["case_id"]) not in public_ids]
        cases = all_scoring
        holdouts_scored = True
    else:
        cases = public_cases
        holdouts_scored = False

    aggregate = score_cases(cases, predictions)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "receipt_id": rid,
        "role": role,
        "holdouts_scored": holdouts_scored,
        "holdout_case_count": len(holdout_cases),
        "public_case_count": len(public_cases),
        "authority_promoted": False,
        "score_subjective": False,
        "opt_woken": False,
        "rl_enabled": False,
        "prime_enabled": False,
        "cases_scored": aggregate["cases_scored"],
        "cases_matched": aggregate["cases_matched"],
        "cases_missed": aggregate["cases_missed"],
        "results": aggregate["results"],
        "config_roots": scoring_cfg.get("case_roots", []),
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise EvalSubstrateError(f"eval-score-receipt-schema-invalid:{exc}") from exc

    out = vault / "generated" / "ops" / "eval" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
