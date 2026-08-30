"""AS-2.2-EVAL-BROKER-001 — adversarial proof suite (D-ULTRA-RESUME-010 §8).

Every test plays the **optimizer/adversary**: it holds only a
:class:`~project_atlas.scoring_broker.ScoringBrokerSession` and the public repo
root. It must be unable to recover the hidden-holdout secrets — expected
answers, real/private case ids, private paths, scoring credentials, or per-case
comparison details — through any channel:

  filesystem enumeration · recursive glob · git-history access · direct module
  import of the private map · environment spoof · role spoof · broker API misuse
  (bound oracle / binary-search) · path disclosure · exception/error-message
  leakage · generated-artifact / receipt inspection · artifact reconstruction.

The test *harness* knows the operator answers (it generated them) ONLY so it can
assert they never leak; the simulated optimizer code never receives them.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from tests.security.git_history_scan import find_leaked_holdout_evidence

from project_atlas import eval_substrate, scoring_broker, scoring_broker_server
from project_atlas.eval_substrate import (
    EVAL_HOLDOUT_EXPECTED_PATH_ENV,
    EVAL_SCORING_CAPABILITY_ENV,
    build_eval_score_receipt,
    holdout_root,
)
from project_atlas.scoring_broker import (
    ScoringBrokerError,
    ScoringBrokerSession,
    open_broker_session,
)

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class OperatorBundle:
    """Operator-side setup. Adversary tests use only ``session`` + REPO_ROOT."""

    session: ScoringBrokerSession
    answers: dict[str, str]  # real case_id -> secret answer (harness-only)
    query_to_answer: dict[str, str]  # public query -> secret answer (harness-only)
    map_path: Path  # out-of-tree private map (harness-only)


def _holdout_case_meta() -> dict[str, dict[str, str]]:
    """Read the committed hidden holdout case metadata (inputs, never answers)."""
    meta: dict[str, dict[str, str]] = {}
    for path in sorted((holdout_root(REPO_ROOT) / "cases").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta[str(payload["case_id"])] = {
            "query": str(payload.get("query", "")),
            "score_mode": str(payload.get("score_mode", "exact")),
        }
    return meta


@pytest.fixture(autouse=True)
def _clear_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    """The adversary's own process never holds the scoring capability."""
    monkeypatch.delenv(EVAL_SCORING_CAPABILITY_ENV, raising=False)
    monkeypatch.delenv(EVAL_HOLDOUT_EXPECTED_PATH_ENV, raising=False)


@pytest.fixture
def broker(tmp_path: Path) -> Iterator[OperatorBundle]:
    meta = _holdout_case_meta()
    answers = {cid: f"answer-{secrets.token_hex(16)}" for cid in meta}
    query_to_answer = {meta[cid]["query"]: answers[cid] for cid in meta}
    private_dir = tmp_path / "operator-private"
    private_dir.mkdir()
    map_path = private_dir / "eval_holdout_expected.json"
    map_path.write_text(json.dumps(answers), encoding="utf-8")
    session = open_broker_session(
        repo_root=REPO_ROOT, expected_map_path=map_path, attempt_budget=8
    )
    try:
        yield OperatorBundle(session, answers, query_to_answer, map_path)
    finally:
        session.close()


def _correct_predictions(
    session: ScoringBrokerSession, query_to_answer: dict[str, str]
) -> dict[str, str]:
    """Operator-only: map opaque ids to correct answers via the public query."""
    return {c.opaque_case_id: query_to_answer[c.query] for c in session.manifest()}


def _raw(session: ScoringBrokerSession, obj: dict[str, Any]) -> dict[str, Any]:
    """Send a raw protocol request, bypassing the client (adversary poking)."""
    proc = session._process
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    parsed = json.loads(line)
    assert isinstance(parsed, dict)
    return parsed


# --------------------------------------------------------------------------- #
# Baseline: the broker is genuinely functional (operator path works).
# --------------------------------------------------------------------------- #
def test_operator_path_scores_correctly(broker: OperatorBundle) -> None:
    result = broker.session.submit(
        _correct_predictions(broker.session, broker.query_to_answer)
    )
    assert result.metrics.cases_scored == len(broker.answers)
    assert result.metrics.cases_matched == len(broker.answers)
    assert result.hard_gates.all_matched is True
    assert result.hard_gates.all_cases_predicted is True


# --------------------------------------------------------------------------- #
# 1. Filesystem enumeration.
# --------------------------------------------------------------------------- #
def test_adv_filesystem_enumeration(broker: OperatorBundle) -> None:
    """Walking the repo tree never surfaces a secret answer; map is out-of-tree."""
    broker.session.submit({})  # drive a scoring run first
    secrets_set = set(broker.answers.values())
    for root, _dirs, files in os.walk(REPO_ROOT):
        if ".git" in Path(root).parts or ".venv" in Path(root).parts:
            continue
        for name in files:
            path = Path(root) / name
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for token in secrets_set:
                assert token not in text, path
    assert not str(broker.map_path.resolve()).startswith(str(REPO_ROOT.resolve()))


# --------------------------------------------------------------------------- #
# 2. Recursive glob.
# --------------------------------------------------------------------------- #
def test_adv_recursive_glob(broker: OperatorBundle) -> None:
    """rglob for holdout case bodies never yields an expected/answer field."""
    for path in REPO_ROOT.rglob("EV-HOLD-*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "expected" not in payload, path
    # No eval/holdout expected-answer map is glob-visible inside the repo.
    pattern = ("eval", "holdout")
    for path in REPO_ROOT.rglob("*expected*.json"):
        if ".venv" in path.parts or ".git" in path.parts:
            continue
        low = path.name.lower()
        assert not any(p in low for p in pattern), path


# --------------------------------------------------------------------------- #
# 3. Git-history access.
# --------------------------------------------------------------------------- #
def test_adv_git_history_access(broker: OperatorBundle) -> None:
    """No secret answer nor a new-holdout expected key exists in ANY history.

    Cluster C redesign (D-CODEX-ATLAS-OWNER-FRONTIER-RESOLUTION-CI-
    CONDITIONAL-INTEGRATION-AND-DAG-CONTINUATION §4/§5/§13): replaces an
    O(secrets * revisions) `git grep <token> <every revision>` scan --
    pathological against this repo's real history (unbounded revision-list
    growth, timed out past 120s without completing) -- with a single
    O(unique historical blobs) pass (`tests/security/git_history_scan.py`;
    see `tests/security/test_git_history_scan_differential.py` for the
    adversarial proof this is not weaker than the original -- it is
    strictly STRONGER: differential testing against synthetic histories
    found the original's `-S` pickaxe check has a real blind spot, missing
    a violation when an existing case file is edited to add its answer
    without changing the case-id string's own occurrence count).
    """
    secret_hits, answer_key_hits = find_leaked_holdout_evidence(
        REPO_ROOT,
        secret_tokens=tuple(broker.answers.values()),
        holdout_case_ids=("EV-HOLD-101", "EV-HOLD-102"),
    )
    assert secret_hits == (), secret_hits
    assert answer_key_hits == (), answer_key_hits


# --------------------------------------------------------------------------- #
# 4. Direct module import of the private map.
# --------------------------------------------------------------------------- #
def test_adv_direct_module_import(broker: OperatorBundle) -> None:
    """Importing broker/substrate modules discloses no answer map or answers."""
    secrets_set = set(broker.answers.values())
    # Import (cached) the modules an adversary would poke; do NOT reload — the
    # security property holds for the live modules, and reloading would swap
    # class identities out from under other tests.
    modules = [importlib.import_module(m.__name__) for m in (
        scoring_broker, scoring_broker_server, eval_substrate,
    )]
    for module in modules:
        blob = json.dumps(
            {k: repr(v) for k, v in vars(module).items()},
            default=repr,
        )
        for token in secrets_set:
            assert token not in blob
        # No module global is an answer map keyed by holdout case id.
        for value in vars(module).values():
            if isinstance(value, dict):
                assert "EV-HOLD-101" not in value
                assert "EV-HOLD-102" not in value
    # Calling the private loader WITHOUT the capability yields no holdout records.
    assert not eval_substrate.scoring_capability_granted()
    assert scoring_broker_server._load_private_records(REPO_ROOT, "salt") == []


# --------------------------------------------------------------------------- #
# 5. Environment spoof.
# --------------------------------------------------------------------------- #
def test_adv_environment_spoof(
    broker: OperatorBundle, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Arming the capability in the adversary's process reveals no real answer."""
    # The adversary fabricates its own map and points the in-process gate at it.
    fake = {"EV-HOLD-101": "guess-a", "EV-HOLD-102": "guess-b"}
    fake_map = tmp_path / "attacker-map.json"
    fake_map.write_text(json.dumps(fake), encoding="utf-8")
    monkeypatch.setenv(EVAL_SCORING_CAPABILITY_ENV, "1")
    monkeypatch.setenv(EVAL_HOLDOUT_EXPECTED_PATH_ENV, str(fake_map))

    # In-process load returns ONLY what the adversary already wrote — never the
    # operator's real secret answers.
    cases = eval_substrate.load_cases(REPO_ROOT, "scoring")
    loaded = {
        str(c["case_id"]): str(c.get("expected", ""))
        for c in cases
        if c.get("visibility") == "holdout"
    }
    assert loaded == fake
    assert set(loaded.values()).isdisjoint(set(broker.answers.values()))

    # The already-running broker (separate process) ignores the adversary's env:
    # scoring reflects the REAL answers, not the adversary's fabricated ones.
    result = broker.session.submit(
        {c.opaque_case_id: "guess-a" for c in broker.session.manifest()}
    )
    assert result.metrics.cases_matched == 0  # fabricated guesses do not match


# --------------------------------------------------------------------------- #
# 6. Role spoof.
# --------------------------------------------------------------------------- #
def test_adv_role_spoof(broker: OperatorBundle) -> None:
    """Injecting privileged-looking fields buys no elevation and no answers."""
    resp = _raw(
        broker.session,
        {
            "op": "submit",
            "role": "operator",
            "reveal_expected": True,
            "elevate": True,
            "predictions": {},
        },
    )
    assert resp["ok"] is True
    assert resp["schema"] == "scoring-broker-result"
    assert "expected" not in json.dumps(resp)
    for token in broker.answers.values():
        assert token not in json.dumps(resp)
    # A privileged-sounding op simply does not exist.
    assert _raw(broker.session, {"op": "reveal_expected"})["error"] == "unknown-op"
    assert _raw(broker.session, {"op": "dump_map"})["error"] == "unknown-op"
    # Manifest with a spoofed role still carries input-only fields.
    man = _raw(broker.session, {"op": "manifest", "role": "operator"})
    assert man["ok"] is True
    for case in man["cases"]:
        assert set(case) == {"opaque_case_id", "score_mode", "query"}


# --------------------------------------------------------------------------- #
# 7. Broker API misuse — bound oracle / binary-search.
# --------------------------------------------------------------------------- #
def test_adv_bound_oracle_binary_search(tmp_path: Path) -> None:
    """A submission budget hard-bounds oracle queries; only aggregates leak."""
    meta = _holdout_case_meta()
    answers = {cid: f"answer-{secrets.token_hex(16)}" for cid in meta}
    map_path = tmp_path / "m.json"
    map_path.write_text(json.dumps(answers), encoding="utf-8")
    budget = 4
    session = open_broker_session(
        repo_root=REPO_ROOT, expected_map_path=map_path, attempt_budget=budget
    )
    try:
        manifest = session.manifest()
        observations: list[int] = []
        for i in range(budget):
            result = session.submit(
                {c.opaque_case_id: f"probe-{i}" for c in manifest}
            )
            # The ONLY signal is an aggregate count — never a per-case flag.
            observations.append(result.metrics.cases_matched)
            assert result.attempts_remaining == budget - (i + 1)
        # Budget exhausted: the oracle is closed. No further probing possible.
        with pytest.raises(ScoringBrokerError, match="attempt-budget-exhausted"):
            session.submit({c.opaque_case_id: "probe-x" for c in manifest})
        # Random probes never matched the high-entropy answers -> no extraction.
        assert observations == [0] * budget
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# 8. Path disclosure.
# --------------------------------------------------------------------------- #
def test_adv_path_disclosure(broker: OperatorBundle) -> None:
    """The session and every broker response are free of the private path."""
    private_path = str(broker.map_path.resolve())
    private_dir = str(broker.map_path.parent.resolve())
    proc = broker.session._process

    surfaces = [
        repr(broker.session),
        json.dumps({k: repr(v) for k, v in vars(broker.session).items()}),
        repr(proc.args),
        json.dumps(_raw(broker.session, {"op": "manifest"})),
        json.dumps(_raw(broker.session, {"op": "submit", "predictions": {}})),
    ]
    for surface in surfaces:
        assert private_path not in surface
        assert private_dir not in surface
        assert "operator-private" not in surface
    # The session retains no private state at all.
    assert set(vars(broker.session)) == {"_process", "_closed"}


# --------------------------------------------------------------------------- #
# 9. Exception / error-message leakage.
# --------------------------------------------------------------------------- #
def test_adv_error_message_leakage(broker: OperatorBundle) -> None:
    """Every error is a fixed sanitized code — no path, answer, or traceback."""
    allowed = scoring_broker_server._ERROR_CODES
    proc = broker.session._process
    assert proc.stdin is not None and proc.stdout is not None

    # Malformed / hostile inputs.
    proc.stdin.write("this is not json\n")
    proc.stdin.flush()
    bad = json.loads(proc.stdout.readline())
    assert bad["error"] in allowed

    cases = [
        {"op": "submit", "predictions": ["not", "a", "map"]},
        {"op": "submit", "predictions": {"x": 5}},
        {"op": "bogus"},
        {"nonsense": True},
    ]
    for req in cases:
        resp = _raw(broker.session, req)
        assert resp["ok"] is False
        assert resp["error"] in allowed
        blob = json.dumps(resp)
        assert "/" not in resp["error"] and "Traceback" not in blob
        for token in broker.answers.values():
            assert token not in blob

    # A broker that fails startup (missing map) leaks no path in its error.
    dead = open_broker_session(
        repo_root=REPO_ROOT,
        expected_map_path=broker.map_path.parent / "does-not-exist.json",
    )
    try:
        resp = _raw(dead, {"op": "manifest"})
        assert resp["error"] == "broker-capability-unavailable"
        assert "does-not-exist" not in json.dumps(resp)
    finally:
        dead.close()


# --------------------------------------------------------------------------- #
# 10. Generated-artifact / receipt inspection.
# --------------------------------------------------------------------------- #
def test_adv_generated_receipt_inspection(
    broker: OperatorBundle, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Durable receipts + broker digest never persist or reconstruct answers."""
    # Operator generates a durable holdout receipt (capability + real map).
    monkeypatch.setenv(EVAL_SCORING_CAPABILITY_ENV, "1")
    monkeypatch.setenv(EVAL_HOLDOUT_EXPECTED_PATH_ENV, str(broker.map_path))
    vault = tmp_path / "vault"
    vault.mkdir()
    predictions = {cid: ans for cid, ans in broker.answers.items()}
    receipt = build_eval_score_receipt(
        vault,
        record_id="adv-receipt",
        repo_root=REPO_ROOT,
        predictions=predictions,
        include_holdouts=True,
    )
    written = (vault / "generated" / "ops" / "eval" / "adv-receipt.json").read_text(
        encoding="utf-8"
    )
    for token in broker.answers.values():
        assert token not in written
    for row in receipt["results"]:
        if row.get("visibility") == "holdout":
            assert row.get("expected_redacted") is True
            assert "predicted_norm" not in row
            assert "matched" not in row
            assert "expected_norm" not in row

    # The broker's own receipt digest is a one-way hash with no answer inside.
    result = broker.session.submit(
        _correct_predictions(broker.session, broker.query_to_answer)
    )
    assert len(result.receipt_digest) == 64
    for token in broker.answers.values():
        assert token not in result.receipt_digest


# --------------------------------------------------------------------------- #
# 11. Artifact reconstruction.
# --------------------------------------------------------------------------- #
def test_adv_artifact_reconstruction(broker: OperatorBundle, tmp_path: Path) -> None:
    """Accumulated opaque ids / digests / metrics cannot rebuild the answers."""
    manifest = broker.session.manifest()
    collected: list[dict[str, Any]] = []
    for i in range(3):
        r = broker.session.submit({c.opaque_case_id: f"try-{i}" for c in manifest})
        collected.append(
            {
                "opaque_case_ids": list(r.opaque_case_ids),
                "digest": r.receipt_digest,
                "matched": r.metrics.cases_matched,
            }
        )
    corpus = json.dumps(collected)
    for token in broker.answers.values():
        assert token not in corpus
    # Opaque ids do not reverse to the real case id via naive hashing.
    for case in manifest:
        oid = case.opaque_case_id
        for real_id in ("EV-HOLD-101", "EV-HOLD-102"):
            assert oid != hashlib.sha256(real_id.encode()).hexdigest()[:32]
        assert oid != hashlib.sha256(case.query.encode()).hexdigest()[:32]
        assert "EV-HOLD" not in oid

    # Cross-session unlinkability: fresh salt -> different opaque ids.
    other = open_broker_session(
        repo_root=REPO_ROOT, expected_map_path=broker.map_path, attempt_budget=2
    )
    try:
        other_ids = {c.opaque_case_id for c in other.manifest()}
    finally:
        other.close()
    assert other_ids.isdisjoint({c.opaque_case_id for c in manifest})
