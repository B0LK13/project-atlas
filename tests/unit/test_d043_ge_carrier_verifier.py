"""D-043 regression tests for GE carrier WORKLOG verifier methodology."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


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


class TestD043VerifierRegression(unittest.TestCase):
    """Minimum D-043 verifier regression suite."""

    def test_utf8_em_dash_is_clean(self) -> None:
        """TEST_UTF8_EM_DASH_IS_CLEAN: E2 80 94 must not count as literal mojibake."""
        sample = bytes.fromhex("E28094")
        self.assertEqual(d042.count_literal_mojibake(sample), 0)

    def test_double_encoded_em_dash_detected(self) -> None:
        """TEST_DOUBLE_ENCODED_EM_DASH_DETECTED."""
        sample = b"text \xc3\xa2\xe2\x82\xac\xe2\x80\x9d more"
        self.assertGreater(d042.count_literal_mojibake(sample), 0)

    def test_clean_d028_does_not_mask_other_corruption(self) -> None:
        """TEST_CLEAN_D028_DOES_NOT_MASK_OTHER_CORRUPTION."""
        clean_d028 = b"## D-028 Golden Estate integration chronology\n"
        corrupted_hist = b"## D-191 \xe2\x80\x94 Atlas 3.0 \xe2\x86\x92 "
        corrupted_new = corrupted_hist.replace(
            b"\xe2\x80\x94", b"\xc3\xa2\xe2\x82\xac\xe2\x80\x9d"
        ).replace(b"\xe2\x86\x92", b"\xc3\xa2\xe2\x82\xac\xe2\x84\xa2")
        combined = clean_d028 + corrupted_new
        self.assertEqual(d042.count_literal_mojibake(clean_d028), 0)
        self.assertGreater(d042.count_literal_mojibake(combined), 0)
        cls, regression = d042.classify_line_pair(corrupted_hist, corrupted_new)
        self.assertTrue(regression)
        self.assertIn(cls, ("ENCODING_ONLY_REWRITE", "UNRELATED_HISTORICAL_REWRITE"))

    def test_unexpected_historical_rewrite_blocks_expected_delta(self) -> None:
        """TEST_UNEXPECTED_HISTORICAL_REWRITE_BLOCKS_EXPECTED_DELTA."""
        old = b"## D-193 governance note \xe2\x80\x94 stable"
        new = b"## D-193 governance note rewritten entirely"
        analysis = d042.DiffAnalysis()
        cls, regression = d042.classify_line_pair(old, new)
        analysis.changed_lines.append(d042.ChangedLine(old, new, cls, regression))
        if cls == "UNRELATED_HISTORICAL_REWRITE":
            analysis.unrelated_historical_rewrite_count += 1
        expected_only = (
            analysis.unrelated_historical_rewrite_count == 0
            and analysis.encoding_only_rewrite_count == 0
            and analysis.unexpected_changed_regions == 0
        )
        self.assertFalse(expected_only)

    def test_encoding_rewrite_flags_carrier_regression(self) -> None:
        """TEST_ENCODING_REWRITE_FLAGS_CARRIER_REGRESSION."""
        old = b"Lane C REPORT READ \xe2\x80\x94 overview"
        new = b"Lane C REPORT READ \xc3\xa2\xe2\x82\xac\xe2\x80\x9d overview"
        cls, regression = d042.classify_line_pair(old, new)
        self.assertTrue(regression)
        self.assertEqual(cls, "EXPECTED_PROVENANCE_RESTORATION")

    def test_merged_pr_not_current_open_closure_target(self) -> None:
        """TEST_MERGED_PR_NOT_CURRENT_OPEN_CLOSURE_TARGET."""
        d043 = _load_module(
            "d043_ge_carrier_reconciliation",
            SCRIPTS / "d043_ge_carrier_reconciliation.py",
        )
        supersession = d043.audit_historical_supersession(d042)
        pr592 = next(
            (e for e in supersession["closure_entries"] if e["PR_NUMBER"] == 592),
            None,
        )
        self.assertIsNotNone(pr592)
        self.assertEqual(pr592["LIVE_STATE"], "MERGED")
        self.assertTrue(pr592["MERGED"])
        self.assertFalse(pr592["ELIGIBLE_FOR_CLOSURE_NOW"])

    def test_carrier_selection_precedes_loser_supersession(self) -> None:
        """TEST_CARRIER_SELECTION_PRECEDES_LOSER_SUPERSESSION."""
        d043 = _load_module(
            "d043_ge_carrier_reconciliation",
            SCRIPTS / "d043_ge_carrier_reconciliation.py",
        )
        packet = d043.build_packet(write_files=False)
        self.assertEqual(packet["canonical_carrier"], "PR608_STACK")
        self.assertFalse(packet.get("pr608_superseded_before_carrier_selection", True))
        self.assertEqual(packet["pr609_disposition"], "SUPERSEDED")


if __name__ == "__main__":
    unittest.main()
