# AS-CODER-ALPHA-CONNECT-PERF-001

| Field | Value |
|---|---|
| Package | `AS-CODER-ALPHA-CONNECT-PERF-001` |
| Module | `src/project_atlas/connect_perf.py` |
| Tests | `tests/unit/test_as_coder_alpha_connect_perf_001.py` |
| Base | stacked on `#374` / `AS-CODER-ALPHA-INCREMENTAL-CONNECT-001` |
| Receipt | `generated/ops/connect-perf-baseline.json` |

## Honesty stamps

```
BASELINE != SLA
PERF != PRODUCT GATE
TELEMETRY != TRUTH CORE
DEMO_FIXTURE != AUTHENTIC_PILOT
INCREMENTAL SKIP != AUTHORITY
MERGE_ELIGIBLE_TO_MAIN = NO
DEPENDENCY_PR = 374
OWNER_MERGE_REQUIRED = YES
```

## Measured lanes

- cold connect
- warm unchanged reconnect
- one-file delta
- brief generation
- context generation
- handoff generation
- source-health
- atlas next

Recorded fields: `wall_ms`, `files_inspected`, `files_reparsed` (ingest invocations),
`records_changed`, `writes`, and process-lifetime `peak_rss_kb` when `resource`
is available.

## Non-claims

- No product SLA is declared from these numbers.
- Cold vs warm is a regression-band observation (`warm_faster` / `warm_equal` /
  `warm_slower` / `unknown`), not a gate.
- Windows stranger timings are not claimed by this Linux measurement.
- This package does not rewrite `connect.py`.
