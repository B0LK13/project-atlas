"""AS-2.2-EVAL-BROKER-001 — out-of-process scoring broker (server side).

This module is the *privileged* half of the scoring broker (D-ULTRA-RESUME-010
§8). It is intended to run as a **separate OS process** (``python -m
project_atlas.scoring_broker_server``) launched by an operator that holds the
holdout scoring capability. The optimizer/caller never runs this code in its
own process; it only talks to it through the thin client in
:mod:`project_atlas.scoring_broker` over stdio.

Trust boundary (why a real process):
  * The broker process alone reads the private expected-answer map and the
    hidden holdout case bodies. Those values live only as **local variables**
    inside :func:`_load_private_records` / :func:`serve` — never module-level
    globals — so importing this module discloses nothing.
  * The broker returns ONLY a bounded result: aggregate metrics, hard gates,
    per-session **opaque** case ids (salted SHA-256, unlinkable across
    sessions), and a one-way receipt digest. It never emits expected answers,
    real case ids, private case contents, filesystem paths, credentials, or
    per-case comparison output.
  * A per-session submission **budget** bounds the oracle: an adversary cannot
    binary-search the answer key by flipping predictions and watching the
    aggregate, because submissions are capped and each yields at most the
    aggregate match count (never per-case matched flags).
  * Every failure is answered with a fixed, sanitized error **code** — never a
    traceback, path, or answer string (defends against error-message leakage).

Determinism / offline: no network, no wall-clock in emitted content; scoring is
a pure function of the submitted predictions within a session.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from project_atlas.eval_substrate import (
    EVAL_HOLDOUT_EXPECTED_PATH_ENV,
    ScoreMode,
    load_cases,
    score_prediction,
    scoring_capability_granted,
)

PACKAGE_ID: Final[str] = "AS-2.2-EVAL-BROKER-001"
RESULT_SCHEMA: Final[str] = "scoring-broker-result"
MANIFEST_SCHEMA: Final[str] = "scoring-broker-manifest"
ERROR_SCHEMA: Final[str] = "scoring-broker-error"

#: Operator-set env carrying the broker's repo root (holdout case bodies).
EVAL_BROKER_REPO_ROOT_ENV: Final[str] = "ATLAS_EVAL_BROKER_REPO_ROOT"
#: Operator-set env carrying the per-session submission budget.
EVAL_BROKER_ATTEMPT_BUDGET_ENV: Final[str] = "ATLAS_EVAL_BROKER_ATTEMPT_BUDGET"

DEFAULT_ATTEMPT_BUDGET: Final[int] = 8

#: The only error codes the broker will ever emit. No dynamic text — a fixed,
#: closed vocabulary guarantees no path/answer/traceback can escape.
_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "broker-capability-unavailable",
        "bad-request",
        "unknown-op",
        "attempt-budget-exhausted",
        "predictions-invalid",
        "broker-internal-error",
    }
)


@dataclass(frozen=True)
class _Record:
    """One private holdout case, held only inside the broker process."""

    real_case_id: str
    opaque_case_id: str
    score_mode: ScoreMode
    query: str
    expected: str


def _opaque_id(salt: str, real_case_id: str) -> str:
    """Per-session, unlinkable opaque id (salted SHA-256, 128-bit hex).

    The salt is fresh per process, so an adversary cannot precompute
    ``sha256(known_case_id)`` nor correlate opaque ids across sessions or with
    git history.
    """
    digest = hashlib.sha256(f"{salt}:{real_case_id}".encode()).hexdigest()
    return digest[:32]


def _load_private_records(repo_root: Path, salt: str) -> list[_Record]:
    """Load hidden holdout cases + expected answers (privileged, in-process).

    Returns records only for ``visibility == "holdout"`` cases. Raises on any
    problem so the caller can fail closed with a generic code.
    """
    cases = load_cases(repo_root, "scoring")
    records: list[_Record] = []
    for case in cases:
        if case.get("visibility") != "holdout":
            continue
        real_id = str(case["case_id"])
        mode_raw = str(case.get("score_mode", "exact"))
        mode: ScoreMode = "prefix" if mode_raw == "prefix" else "exact"
        records.append(
            _Record(
                real_case_id=real_id,
                opaque_case_id=_opaque_id(salt, real_id),
                score_mode=mode,
                query=str(case.get("query", "")),
                expected=str(case["expected"]),
            )
        )
    records.sort(key=lambda r: r.opaque_case_id)
    return records


def _error(code: str) -> dict[str, Any]:
    safe = code if code in _ERROR_CODES else "broker-internal-error"
    return {"ok": False, "schema": ERROR_SCHEMA, "error": safe}


def _manifest_response(records: list[_Record], attempts_remaining: int) -> dict[str, Any]:
    """Input-only manifest: opaque id + score mode + public query. No answers."""
    return {
        "ok": True,
        "schema": MANIFEST_SCHEMA,
        "cases": [
            {
                "opaque_case_id": r.opaque_case_id,
                "score_mode": r.score_mode,
                "query": r.query,
            }
            for r in records
        ],
        "attempts_remaining": attempts_remaining,
    }


def _receipt_digest(
    records: list[_Record], *, matched: int, attempt_index: int
) -> str:
    """One-way digest of the scoring run. Carries no answer string outward."""
    payload = json.dumps(
        {
            "package_id": PACKAGE_ID,
            "real_case_ids": sorted(r.real_case_id for r in records),
            "cases_scored": len(records),
            "cases_matched": matched,
            "attempt_index": attempt_index,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _score_submission(
    records: list[_Record],
    predictions: dict[str, str],
    *,
    attempts_remaining_after: int,
    attempt_index: int,
) -> dict[str, Any]:
    """Score predictions (keyed by opaque id) into a bounded result.

    Only aggregate counts leave this function — never per-case matched flags,
    expected answers, or predicted strings.
    """
    matched = 0
    predicted_count = 0
    for record in records:
        predicted = predictions.get(record.opaque_case_id, "")
        if record.opaque_case_id in predictions:
            predicted_count += 1
        outcome = score_prediction(
            expected=record.expected, predicted=predicted, mode=record.score_mode
        )
        if outcome["matched"]:
            matched += 1
    scored = len(records)
    return {
        "ok": True,
        "schema": RESULT_SCHEMA,
        "metrics": {
            "cases_scored": scored,
            "cases_matched": matched,
            "cases_missed": scored - matched,
        },
        "hard_gates": {
            "all_cases_predicted": predicted_count == scored,
            "all_matched": matched == scored and scored > 0,
            "budget_ok": True,
        },
        "opaque_case_ids": [r.opaque_case_id for r in records],
        "receipt_digest": _receipt_digest(
            records, matched=matched, attempt_index=attempt_index
        ),
        "attempts_remaining": attempts_remaining_after,
    }


def _coerce_predictions(raw: Any) -> dict[str, str] | None:
    """Accept only a flat {opaque_id: string} map; reject anything else."""
    if not isinstance(raw, dict):
        return None
    out: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return None
        out[key] = value
    return out


def _emit(stream: Any, payload: dict[str, Any]) -> None:
    stream.write(json.dumps(payload, sort_keys=True) + "\n")
    stream.flush()


def serve(
    stdin: Any,
    stdout: Any,
    *,
    repo_root: Path | None = None,
    attempt_budget: int = DEFAULT_ATTEMPT_BUDGET,
) -> int:
    """Run the broker request loop over the given text streams.

    Returns a process exit code. Fail-closed: if the holdout scoring capability
    is not armed in *this* process's environment, every request is answered with
    ``broker-capability-unavailable`` and no case bodies are ever loaded.
    """
    salt = secrets.token_hex(16)
    records: list[_Record] | None = None
    startup_code: str | None = None
    if not scoring_capability_granted() or not os.environ.get(
        EVAL_HOLDOUT_EXPECTED_PATH_ENV, ""
    ).strip():
        startup_code = "broker-capability-unavailable"
    else:
        root = repo_root or Path(
            os.environ.get(EVAL_BROKER_REPO_ROOT_ENV, "") or "."
        )
        try:
            records = _load_private_records(root.resolve(), salt)
        except Exception:  # never leak the cause outward
            records = None
            startup_code = "broker-capability-unavailable"

    attempts_remaining = max(0, attempt_budget)

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            _emit(stdout, _error("bad-request"))
            continue
        if not isinstance(request, dict):
            _emit(stdout, _error("bad-request"))
            continue

        op = request.get("op")
        # Extra/spoofed fields (e.g. role, reveal_expected) are ignored: the
        # protocol has no privileged op, so role/env spoof buys nothing.
        try:
            if records is None:
                _emit(stdout, _error(startup_code or "broker-capability-unavailable"))
                continue
            if op == "close":
                break
            if op == "manifest":
                _emit(stdout, _manifest_response(records, attempts_remaining))
                continue
            if op == "submit":
                if attempts_remaining <= 0:
                    _emit(stdout, _error("attempt-budget-exhausted"))
                    continue
                predictions = _coerce_predictions(request.get("predictions"))
                if predictions is None:
                    _emit(stdout, _error("predictions-invalid"))
                    continue
                attempts_remaining -= 1
                attempt_index = attempt_budget - attempts_remaining
                _emit(
                    stdout,
                    _score_submission(
                        records,
                        predictions,
                        attempts_remaining_after=attempts_remaining,
                        attempt_index=attempt_index,
                    ),
                )
                continue
            _emit(stdout, _error("unknown-op"))
        except Exception:  # sanitized code only, never a trace
            _emit(stdout, _error("broker-internal-error"))
    return 0


def main() -> int:
    budget_raw = os.environ.get(EVAL_BROKER_ATTEMPT_BUDGET_ENV, "").strip()
    try:
        budget = int(budget_raw) if budget_raw else DEFAULT_ATTEMPT_BUDGET
    except ValueError:
        budget = DEFAULT_ATTEMPT_BUDGET
    return serve(sys.stdin, sys.stdout, attempt_budget=budget)


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
