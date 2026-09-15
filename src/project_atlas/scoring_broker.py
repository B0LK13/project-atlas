"""AS-2.2-EVAL-BROKER-001 — out-of-process scoring broker (client library).

The true trust boundary for hidden-holdout scoring (D-ULTRA-RESUME-010 §8).

Privilege split:
  * :func:`open_broker_session` is **operator** code. It knows where the private
    expected-answer map lives and launches the broker as a *separate process*
    (:mod:`project_atlas.scoring_broker_server`) with the holdout scoring
    capability armed in the child's environment only. It returns a
    :class:`ScoringBrokerSession`.
  * :class:`ScoringBrokerSession` is the **optimizer** handle. It exposes only
    :meth:`manifest` (input-only cases) and :meth:`submit` (candidate outputs ->
    bounded result). It retains no expected answers, no private paths, no
    credentials, and no environment — only the subprocess pipes.

What the optimizer can obtain: aggregate metrics, hard gates, per-session opaque
case ids, a one-way receipt digest, and the remaining submission budget.

What the optimizer can NEVER obtain through this API (or the process channel):
expected answers, private/real case ids, private case contents, private
filesystem paths, scoring credentials, or per-case comparison details.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Final

from project_atlas.eval_substrate import (
    EVAL_HOLDOUT_EXPECTED_PATH_ENV,
    EVAL_SCORING_CAPABILITY_ENV,
)
from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.scoring_broker_server import (
    DEFAULT_ATTEMPT_BUDGET,
    EVAL_BROKER_ATTEMPT_BUDGET_ENV,
    EVAL_BROKER_REPO_ROOT_ENV,
)

PACKAGE_ID: Final[str] = "AS-2.2-EVAL-BROKER-001"
_RESULT_SCHEMA_KIND: Final[str] = "scoring-broker-result"


class ScoringBrokerError(RuntimeError):
    """Raised for a bounded broker error code or a broken broker channel.

    The message is always a fixed error code — never a path, answer, or trace.
    """


@dataclass(frozen=True)
class BrokerCase:
    """One input-only manifest entry (no expected answer)."""

    opaque_case_id: str
    score_mode: str
    query: str


@dataclass(frozen=True)
class BrokerMetrics:
    cases_scored: int
    cases_matched: int
    cases_missed: int


@dataclass(frozen=True)
class BrokerHardGates:
    all_cases_predicted: bool
    all_matched: bool
    budget_ok: bool


@dataclass(frozen=True)
class BrokerResult:
    """Bounded scoring result — the only scoring signal an optimizer receives."""

    metrics: BrokerMetrics
    hard_gates: BrokerHardGates
    opaque_case_ids: tuple[str, ...]
    receipt_digest: str
    attempts_remaining: int


class ScoringBrokerSession:
    """Optimizer-facing handle over a running broker subprocess.

    Holds only the subprocess pipes. It deliberately stores no private path,
    expected map, credential, or environment, so inspecting the object (``vars``,
    ``__dict__``, ``repr``) discloses nothing about the holdout secrets.
    """

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process
        self._closed = False

    def __enter__(self) -> ScoringBrokerSession:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _roundtrip(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._closed:
            raise ScoringBrokerError("broker-closed")
        proc = self._process
        if proc.stdin is None or proc.stdout is None:
            raise ScoringBrokerError("broker-unavailable")
        try:
            proc.stdin.write(json.dumps(request, sort_keys=True) + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, ValueError) as exc:
            raise ScoringBrokerError("broker-unavailable") from exc
        line = proc.stdout.readline()
        if not line:
            raise ScoringBrokerError("broker-unavailable")
        try:
            response = json.loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ScoringBrokerError("broker-protocol-error") from exc
        if not isinstance(response, dict):
            raise ScoringBrokerError("broker-protocol-error")
        if response.get("ok") is not True:
            code = response.get("error")
            raise ScoringBrokerError(str(code) if isinstance(code, str) else "bad-request")
        return response

    def manifest(self) -> list[BrokerCase]:
        """Return the input-only case manifest (no expected answers)."""
        response = self._roundtrip({"op": "manifest"})
        raw_cases = response.get("cases")
        if not isinstance(raw_cases, list):
            raise ScoringBrokerError("broker-protocol-error")
        cases: list[BrokerCase] = []
        for item in raw_cases:
            if not isinstance(item, dict):
                raise ScoringBrokerError("broker-protocol-error")
            cases.append(
                BrokerCase(
                    opaque_case_id=str(item.get("opaque_case_id", "")),
                    score_mode=str(item.get("score_mode", "")),
                    query=str(item.get("query", "")),
                )
            )
        return cases

    def submit(
        self,
        predictions: Mapping[str, str],
        *,
        candidate: Mapping[str, Any] | None = None,
    ) -> BrokerResult:
        """Submit candidate outputs (keyed by opaque id); get a bounded result.

        ``candidate`` is optional opaque config metadata forwarded to the broker
        and never echoed back. The broker decrements the submission budget and
        returns aggregate metrics only.
        """
        request: dict[str, Any] = {
            "op": "submit",
            "predictions": {str(k): str(v) for k, v in predictions.items()},
        }
        if candidate is not None:
            request["candidate"] = dict(candidate)
        response = self._roundtrip(request)
        # Defense in depth: the client refuses any response that does not match
        # the bounded schema (additionalProperties:false), so a broker that ever
        # tried to attach answers would be rejected here too.
        try:
            validate_record(response, _RESULT_SCHEMA_KIND)
        except SchemaValidationError as exc:
            raise ScoringBrokerError("broker-result-unbounded") from exc
        metrics = response["metrics"]
        gates = response["hard_gates"]
        return BrokerResult(
            metrics=BrokerMetrics(
                cases_scored=int(metrics["cases_scored"]),
                cases_matched=int(metrics["cases_matched"]),
                cases_missed=int(metrics["cases_missed"]),
            ),
            hard_gates=BrokerHardGates(
                all_cases_predicted=bool(gates["all_cases_predicted"]),
                all_matched=bool(gates["all_matched"]),
                budget_ok=bool(gates["budget_ok"]),
            ),
            opaque_case_ids=tuple(str(cid) for cid in response["opaque_case_ids"]),
            receipt_digest=str(response["receipt_digest"]),
            attempts_remaining=int(response["attempts_remaining"]),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        proc = self._process
        try:
            if proc.stdin is not None and not proc.stdin.closed:
                try:
                    proc.stdin.write(json.dumps({"op": "close"}) + "\n")
                    proc.stdin.flush()
                except (BrokenPipeError, ValueError):
                    pass
                proc.stdin.close()
        finally:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
            for stream in (proc.stdout, proc.stderr):
                if stream is not None and not stream.closed:
                    stream.close()


def open_broker_session(
    *,
    repo_root: Path,
    expected_map_path: Path,
    attempt_budget: int = DEFAULT_ATTEMPT_BUDGET,
    python_executable: str | None = None,
) -> ScoringBrokerSession:
    """Operator-privileged launch of the broker in a separate process.

    Arms the holdout scoring capability in the **child** environment only and
    returns an optimizer-safe :class:`ScoringBrokerSession`. The private
    ``expected_map_path`` is passed to the child env here and is never attached
    to the returned session.
    """
    child_env = dict(os.environ)
    child_env[EVAL_SCORING_CAPABILITY_ENV] = "1"
    child_env[EVAL_HOLDOUT_EXPECTED_PATH_ENV] = str(Path(expected_map_path).resolve())
    child_env[EVAL_BROKER_REPO_ROOT_ENV] = str(Path(repo_root).resolve())
    child_env[EVAL_BROKER_ATTEMPT_BUDGET_ENV] = str(max(0, int(attempt_budget)))
    process = subprocess.Popen(
        [python_executable or sys.executable, "-m", "project_atlas.scoring_broker_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=child_env,
        cwd=str(Path(repo_root).resolve()),
    )
    return ScoringBrokerSession(process)
