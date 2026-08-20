# AS-CI-WINDOWS-PERF-GATE-001

```
PACKAGE = AS-CI-WINDOWS-PERF-GATE-001
DIRECTIVE = D-CLOUD-WINDOWS-PERF-GATE-REMEDIATION-034
BASE = 5b7f564863d09d82fb7977cfc495f5a2b5124f6b
DRAFT = YES
CERTIFICATION = NOT_GRANTED
MERGE_AUTHORIZATION = NOT_GRANTED
INDEPENDENT_IV = BLOCKED
SELF_REVIEW != INDEPENDENT_IV
PRODUCT_PERFORMANCE_THRESHOLD_CHANGED = NO
PRODUCT_IMPLEMENTATION_CHANGED = NO
```

Windows hosted CI failed the dense-10k wall-clock (`elapsed < 20.0`) in
the 20.038–24.685s range under default `addopts` coverage instrumentation.
The same tests pass uncovered on Windows. Unrelated stale-lens PRs hit the
same test without touching `contradictions.py`.

Remediation: mark the two dense-10k product-perf tests and run them on
Windows with `--no-cov` before the normal coverage suite
(`-m "not product_perf"`). Linux full/compat still run the 20s gate.

```
WINDOWS_MEASUREMENT_MODE =
  COVERAGE-INSTRUMENTED WALLCLOCK
  → ISOLATED UNCOVERED PRODUCT PERF GATE
WHY = ORIGINAL 20S BOUND WAS CALIBRATED UNCOVERED
DENSE_10K_PRODUCT_CAP_SECONDS = 20.0
LINUX_PERF_THRESHOLD = 20.0
```
