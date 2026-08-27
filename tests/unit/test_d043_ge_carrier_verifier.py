"""D-043 regression tests for GE carrier WORKLOG verifier methodology."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"

ISOLATED_EXTERNAL_CALL_COUNT = 0


def _forbidden_external(*_args, **_kwargs):
    global ISOLATED_EXTERNAL_CALL_COUNT
    ISOLATED_EXTERNAL_CALL_COUNT += 1
    raise AssertionError("External call forbidden in isolated governance test")


def _load_module(module_name: str, path: Path):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


d042 = _load_module(
    "d042_competing_d038_methodology_reconciliation",
    SCRIPTS / "d042_competing_d038_methodology_reconciliation.py",
)
contracts = _load_module(
    "d043_governance_contracts",
    SCRIPTS / "d043_governance_contracts.py",
)


class TestD043EncodingMetrics(unittest.TestCase):
    """Byte-level encoding metrics (no network)."""

    def test_utf8_em_dash_is_clean(self) -> None:
        """TEST_UTF8_EM_DASH_IS_CLEAN: E2 80 94 must not count as literal mojibake."""
        sample = bytes.fromhex("E28094")
        self.assertEqual(d042.count_literal_mojibake(sample), 0)

    def test_double_encoded_em_dash_detected(self) -> None:
        """TEST_DOUBLE_ENCODED_EM_DASH_DETECTED."""
        sample = b"text \xc3\xa2\xe2\x82\xac\xe2\x80\x9d more"
        self.assertGreater(d042.count_literal_mojibake(sample), 0)


class TestD043IsolatedGovernanceContracts(unittest.TestCase):
    """Fixture-driven governance contracts — no git, gh, or network."""

    def setUp(self) -> None:
        global ISOLATED_EXTERNAL_CALL_COUNT
        ISOLATED_EXTERNAL_CALL_COUNT = 0
        self._patches = [
            patch.object(
                d042,
                "fetch_all_pr_states",
                side_effect=_forbidden_external,
            ),
            patch.object(
                d042,
                "gh_pr_state",
                side_effect=_forbidden_external,
            ),
            patch.object(
                subprocess,
                "check_output",
                side_effect=_forbidden_external,
            ),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()

    def test_clean_d028_does_not_mask_other_corruption(self) -> None:
        """TEST_CLEAN_D028_DOES_NOT_MASK_OTHER_CORRUPTION."""
        clean_d028_only = contracts.worklog_summary_from_counts()
        self.assertFalse(contracts.carrier_has_worklog_regression(clean_d028_only))

        with_regression_elsewhere = contracts.worklog_summary_from_counts(
            encoding_regression_count=1,
        )
        self.assertTrue(contracts.carrier_has_worklog_regression(with_regression_elsewhere))

        with_encoding_only_rewrite = contracts.worklog_summary_from_counts(
            encoding_only_rewrite_count=1,
        )
        self.assertTrue(contracts.carrier_has_worklog_regression(with_encoding_only_rewrite))
        self.assertFalse(contracts.expected_worklog_delta_only(with_encoding_only_rewrite))

    def test_unexpected_historical_rewrite_blocks_expected_delta(self) -> None:
        """TEST_UNEXPECTED_HISTORICAL_REWRITE_BLOCKS_EXPECTED_DELTA."""
        analysis = contracts.worklog_summary_from_counts(
            unrelated_historical_rewrite_count=1,
        )
        self.assertFalse(contracts.expected_worklog_delta_only(analysis))

    def test_encoding_rewrite_flags_carrier_regression(self) -> None:
        """TEST_ENCODING_REWRITE_FLAGS_CARRIER_REGRESSION."""
        analysis = contracts.worklog_summary_from_counts(encoding_regression_count=1)
        self.assertTrue(contracts.carrier_has_worklog_regression(analysis))

    def test_merged_pr_not_open_closure_target(self) -> None:
        """TEST_MERGED_PR_NOT_OPEN_CLOSURE_TARGET."""
        pr592_fixture = {"PR_NUMBER": 592, "LIVE_STATE": "MERGED", "MERGED": True}
        self.assertFalse(
            contracts.closure_eligible(
                pr592_fixture["LIVE_STATE"],
                merged=pr592_fixture["MERGED"],
            )
        )

    def test_carrier_selection_precedes_loser_supersession(self) -> None:
        """TEST_CARRIER_SELECTION_PRECEDES_LOSER_SUPERSESSION."""
        decision = contracts.choose_canonical_carrier(
            pr608_worklog_regression=False,
            pr609_worklog_regression=True,
            ge_equivalent=True,
            ci_equivalent=True,
        )
        self.assertEqual(decision.canonical_carrier, "PR608_STACK")
        self.assertEqual(decision.pr607_disposition, "REQUIRED_BEFORE_CANONICAL_CARRIER")
        self.assertEqual(decision.pr608_disposition, "CANONICAL_AFTER_PR607")
        self.assertEqual(decision.pr609_disposition, "SUPERSEDED")
        self.assertEqual(decision.canonical_ge_carrier_ambiguity, 0)


class TestD043FullVerifierReproduction(unittest.TestCase):
    """Full verifier dry-run (uses git/gh — not part of isolated contract suite)."""

    def test_full_d043_dry_run_canonical_unchanged(self) -> None:
        d043 = _load_module(
            "d043_ge_carrier_reconciliation",
            SCRIPTS / "d043_ge_carrier_reconciliation.py",
        )
        packet = d043.build_packet(write_files=False)
        self.assertEqual(packet["canonical_carrier"], "PR608_STACK")
        self.assertTrue(packet["pr609_worklog_carrier_regression"])
        self.assertFalse(packet["pr608_worklog_carrier_regression"])
        self.assertTrue(packet["ge_byte_equivalence"])
        self.assertTrue(packet["ci_608_609_semantic_equivalence"])
        self.assertEqual(packet["canonical_ge_carrier_ambiguity"], 0)


if __name__ == "__main__":
    unittest.main()
