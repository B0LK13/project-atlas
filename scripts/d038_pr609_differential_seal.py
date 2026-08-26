#!/usr/bin/env python3
"""D-038: PR609 differential seal — INVALIDATED by D-042.

METHODOLOGY_VALID = NO. Do not use for carrier decisions.
Use scripts/d042_competing_d038_methodology_reconciliation.py instead.

Invalidation reasons:
  CP1252_REDECODE_FALSE_BASELINE
  INCOMPLETE_CARRIER_DIFF_SCOPE
  EXPECTED_DELTA_ONLY_LOGIC_ERROR
  STALE_PR_STATE_IN_SUPERSESSION_COUNT
  CIRCULAR_PR608_SUPERSESSION

Forensic record preserved in docs/evidence/D-AUG26-PR609-FINAL-DIFFERENTIAL-SEAL-038.json
with methodology_valid=false additive stamp.
"""
from __future__ import annotations

import sys


def main() -> None:
    print(
        "ERROR: D-038 script METHODOLOGY_VALID=NO — invalidated by D-042. "
        "Run scripts/d042_competing_d038_methodology_reconciliation.py",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
