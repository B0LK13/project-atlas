# AS-CODER-ALPHA-WORKFLOW-METRICS-001

| Field | Value |
|---|---|
| Package | `AS-CODER-ALPHA-WORKFLOW-METRICS-001` |
| Module | `src/project_atlas/workflow_metrics.py` |
| Tests | `tests/unit/test_as_coder_alpha_workflow_metrics_001.py` |
| Receipt | `generated/ops/workflow-metrics.json` (ops telemetry, not Truth Core) |

## Honesty stamps

```
TELEMETRY != TRUTH CORE
UNKNOWN != 0
NOT_INSTRUMENTED != 0
DEMO_FIXTURE != AUTHENTIC_PILOT
RAW_PROMPT_CAPTURE = NO
CHAT_TRANSCRIPT_CAPTURE = NO
```

## Metric instrumentation

| Metric | When MEASURED | Otherwise |
|---|---|---|
| `TIME_TO_USEFUL_CONTEXT` | Never from current connect receipts (no wall-clock; NFR-001) | `NOT_INSTRUMENTED` |
| `HANDOFF_SUCCESS_RATE` | Only if `resume-*.json` receipts exist | `UNKNOWN` (create packs alone are not a success rate) |
| `STALE_CONTEXT_RATE` | Average of `metrics.STALE_CONTEXT_RATE` on freshness receipts | `UNKNOWN` if those receipts are absent |
| `UNKNOWN_HONESTY` | Average of `metrics.UNKNOWN_HONESTY` on fresh-agent receipts | `UNKNOWN` if absent |
| `MEANINGFUL_CHANGES_CAPTURED` | Count of session-capture receipts with non-empty `changes` when the capture directory exists | `UNKNOWN` if the directory is absent (missing instrument ≠ 0) |
| `USER_CORRECTIONS_REQUIRED` | — | `NOT_INSTRUMENTED` (no owner-edit receipt) |
| `MISTAKES_PREVENTED` | — | `NOT_INSTRUMENTED` (no block/gate prevention receipt) |
| `REEXPLANATION_RATE` | Fraction of fresh-agent receipts with `reexplanation_required=true` | `UNKNOWN` if those receipts are absent |

Unmeasured metrics carry `value: null`. The compiler refuses to attach a numeric value (including `0`) to `UNKNOWN` or `NOT_INSTRUMENTED`.

## Privacy

The compiler reads structured ops receipts only (handoff ids, capture change lists, numeric score fields). It does not ingest raw prompts or chat transcripts to compute a metric.

## Non-claims

- These numbers are not Layer B authority.
- Absence of a receipt is not a healthy zero.
- This package does not rewrite `connect.py` or add wall-clock timestamps.
