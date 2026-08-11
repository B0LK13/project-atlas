"""AS-2.2-EVAL-001 — eval substrate holdout isolation + scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pytest

from project_atlas.eval_substrate import (
    EVAL_HOLDOUT_EXPECTED_PATH_ENV,
    EVAL_SCORING_CAPABILITY_ENV,
    EvalSubstrateError,
    assert_path_readable,
    build_eval_score_receipt,
    holdout_root,
    list_case_files,
    load_cases,
    load_role_config,
    score_prediction,
    scoring_capability_granted,
)
from project_atlas.schema import available_schemas, validate_record

REPO_ROOT = Path(__file__).resolve().parents[2]
HOLDOUT_EXPECTED_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "eval_holdout_expected.json"


@pytest.fixture
def scoring_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EVAL_SCORING_CAPABILITY_ENV, "1")
    monkeypatch.setenv(
        EVAL_HOLDOUT_EXPECTED_PATH_ENV,
        str(HOLDOUT_EXPECTED_FIXTURE),
    )


@pytest.fixture(autouse=True)
def clear_scoring_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EVAL_SCORING_CAPABILITY_ENV, raising=False)
    monkeypatch.delenv(EVAL_HOLDOUT_EXPECTED_PATH_ENV, raising=False)


def test_docs_and_schema_registered() -> None:
    assert (REPO_ROOT / "docs" / "AS-2.2-EVAL-001.md").is_file()
    assert "eval-score-receipt" in available_schemas()


def test_training_and_autolab_see_public_only() -> None:
    training = load_cases(REPO_ROOT, "training")
    autolab = load_cases(REPO_ROOT, "autolab")
    assert {c["case_id"] for c in training} == {"EV-PUB-001", "EV-PUB-002"}
    assert {c["case_id"] for c in autolab} == {"EV-PUB-001", "EV-PUB-002"}
    roles: tuple[Literal["training", "autolab"], ...] = ("training", "autolab")
    for role in roles:
        ids = {p.name for p in list_case_files(REPO_ROOT, role)}
        assert not any(name.startswith("EV-HOLD-") for name in ids)


def test_scoring_without_capability_is_public_only() -> None:
    assert not scoring_capability_granted()
    cases = load_cases(REPO_ROOT, "scoring")
    assert {c["case_id"] for c in cases} == {"EV-PUB-001", "EV-PUB-002"}


def test_scoring_sees_holdouts_with_capability(scoring_capability: None) -> None:
    cases = load_cases(REPO_ROOT, "scoring")
    ids = {c["case_id"] for c in cases}
    assert "EV-PUB-001" in ids
    assert "EV-HOLD-001" in ids
    assert "EV-HOLD-002" in ids
    hold = next(c for c in cases if c["case_id"] == "EV-HOLD-001")
    assert hold["expected"] == "conflict-detected"


def test_holdout_git_case_files_have_no_plaintext_expected() -> None:
    for path in sorted((holdout_root(REPO_ROOT) / "cases").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "expected" not in payload, path.name


def test_holdout_path_blocked_for_training_autolab() -> None:
    hidden = holdout_root(REPO_ROOT) / "cases" / "EV-HOLD-001-exact.json"
    assert hidden.is_file()
    with pytest.raises(EvalSubstrateError, match="holdout-isolated:training"):
        assert_path_readable(REPO_ROOT, "training", hidden)
    with pytest.raises(EvalSubstrateError, match="holdout-isolated:autolab"):
        assert_path_readable(REPO_ROOT, "autolab", hidden)


def test_holdout_path_requires_capability_for_scoring() -> None:
    hidden = holdout_root(REPO_ROOT) / "cases" / "EV-HOLD-001-exact.json"
    with pytest.raises(EvalSubstrateError, match="holdout-capability-required"):
        assert_path_readable(REPO_ROOT, "scoring", hidden)


def test_training_config_rejects_holdout_root(tmp_path: Path) -> None:
    eval_root = tmp_path / "fixtures" / "eval"
    (eval_root / "public" / "cases").mkdir(parents=True)
    (eval_root / "holdouts" / "hidden" / "cases").mkdir(parents=True)
    (eval_root / "configs").mkdir(parents=True)
    (eval_root / "public" / "cases" / "EV-PUB-001-exact.json").write_text(
        json.dumps(
            {
                "case_id": "EV-PUB-001",
                "visibility": "public",
                "score_mode": "exact",
                "expected": "ok",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (eval_root / "configs" / "training.paths.json").write_text(
        json.dumps(
            {
                "role": "training",
                "package_id": "AS-2.2-EVAL-001",
                "case_roots": ["fixtures/eval/holdouts/hidden"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(EvalSubstrateError, match="holdout-isolated:training-config"):
        load_role_config(tmp_path, "training")


def test_deterministic_scoring_hooks() -> None:
    exact = score_prediction(expected="Validate-OK", predicted="validate-ok", mode="exact")
    assert exact["matched"] is True
    prefix = score_prediction(expected="discover-", predicted="discover-ok", mode="prefix")
    assert prefix["matched"] is True
    miss = score_prediction(expected="a", predicted="b", mode="exact")
    assert miss["matched"] is False


def test_score_receipt_public_only(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    receipt = build_eval_score_receipt(
        vault,
        record_id="eval-pub",
        repo_root=REPO_ROOT,
        predictions={
            "EV-PUB-001": "validate-ok",
            "EV-PUB-002": "discover-manifest",
        },
        include_holdouts=False,
    )
    assert receipt["holdouts_scored"] is False
    assert receipt["opt_woken"] is False
    assert receipt["cases_matched"] == 2
    validate_record(receipt, "eval-score-receipt")
    assert (vault / "generated" / "ops" / "eval" / "eval-pub.json").is_file()


def test_score_receipt_with_holdouts(
    tmp_path: Path,
    scoring_capability: None,
) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    receipt = build_eval_score_receipt(
        vault,
        record_id="eval-hold",
        repo_root=REPO_ROOT,
        predictions={
            "EV-PUB-001": "validate-ok",
            "EV-PUB-002": "discover-x",
            "EV-HOLD-001": "conflict-detected",
            "EV-HOLD-002": "lineage-stable",
        },
        include_holdouts=True,
    )
    assert receipt["holdouts_scored"] is True
    assert receipt["holdout_case_count"] == 2
    assert receipt["cases_scored"] == 4
    assert receipt["cases_matched"] == 4
    holdout_rows = [r for r in receipt["results"] if r["visibility"] == "holdout"]
    assert holdout_rows
    for row in holdout_rows:
        assert row["expected_norm"] == ""
        assert row["expected_redacted"] is True
    validate_record(receipt, "eval-score-receipt")


def test_include_holdouts_requires_capability(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(EvalSubstrateError, match="holdout-capability-required"):
        build_eval_score_receipt(
            vault,
            record_id="eval-no-cap",
            repo_root=REPO_ROOT,
            predictions={},
            include_holdouts=True,
        )


def test_opt_wake_refused(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(EvalSubstrateError, match="opt-gated"):
        build_eval_score_receipt(
            vault,
            record_id="eval-opt",
            repo_root=REPO_ROOT,
            predictions={},
            wake_opt=True,
        )


def test_rl_prime_invent_refused(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(EvalSubstrateError, match="forbidden-claim:rl"):
        build_eval_score_receipt(
            vault,
            record_id="eval-rl",
            repo_root=REPO_ROOT,
            predictions={},
            rl=True,
        )
    with pytest.raises(EvalSubstrateError, match="forbidden-claim:prime"):
        build_eval_score_receipt(
            vault,
            record_id="eval-prime",
            repo_root=REPO_ROOT,
            predictions={},
            prime=True,
        )
    with pytest.raises(EvalSubstrateError, match="forbidden-claim:invent_pilot"):
        build_eval_score_receipt(
            vault,
            record_id="eval-pilot",
            repo_root=REPO_ROOT,
            predictions={},
            invent_pilot=True,
        )
