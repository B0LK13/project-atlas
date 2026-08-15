# AS-CODER-ALPHA-CONTEXT-FRESHNESS-ADV-001

| Field | Value |
|---|---|
| Package | `AS-CODER-ALPHA-CONTEXT-FRESHNESS-ADV-001` |
| Module | `src/project_atlas/context_freshness_adv.py` |
| Tests | `tests/unit/test_as_coder_alpha_context_freshness_adv_001.py` |
| Kind | Adversarial regression harness (library + pytest) |
| `connect.py` | Not rewritten. No-change reconnect is library-only. |

## Honesty stamps

```
DEMO_FIXTURE != AUTHENTIC_PILOT
UNKNOWN != HEALTHY
TELEMETRY != TRUTH CORE
CONNECT_PY_REWRITTEN = NO
```

## Covered adversarial cases

| Case | Detection |
|---|---|
| Governing decision becomes superseded | `superseded_as_governing` |
| Source deleted after context generation | `stale_source` |
| Source modified after handoff | `stale_source` |
| Conflicting source introduced | `missing_conflict` |
| Source-health failure introduced | `source_health_gap` |
| Two projects share filenames / similar titles | `cross_project_leak` when sibling tokens appear |
| Quarantined capture references another project | `cross_project_leak` |
| Stale generated answer exists | `stale_generated_answer` |
| Malformed generated artifact | `malformed_artifact` + `unknown_suppression` if claimed healthy |
| No-change reconnect honesty | Library compare of source fingerprints. `UNKNOWN` when fingerprints are absent — never faked. Does not call or rewrite `connect.py`. |

## Invariants (covered cases)

```
STALE_CONTEXT_FALSE_NEGATIVE = 0
CROSS_PROJECT_LEAK_COUNT = 0   # for correctly scoped packs
SUPERSEDED_AS_GOVERNING = 0    # for current-correct packs
UNKNOWN_SUPPRESSION = 0        # unless the case is the suppression itself
SECRET_ECHO = 0                # unless the case injects a secret-shaped span
```

## Non-claims

- This package does not change `connect.py`, CLI, MCP, or Web.
- Receipts under `generated/ops/context-freshness/` are not Truth Core.
- `UNKNOWN` reconnect honesty is not a pass.
