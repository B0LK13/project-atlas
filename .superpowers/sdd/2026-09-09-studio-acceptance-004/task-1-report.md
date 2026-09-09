# Task 1 report: frontend contract, freshness, and cancellation

## Scope

Owned files:

- `apps/studio/src/data/adapter.ts`
- `apps/studio/src/data/adapter.test.ts`
- `apps/studio/src/data/useStudioData.ts`
- `apps/studio/src/data/useStudioData.test.tsx`
- `apps/studio/src/data/test-fixtures/generated-a1-packet.json`
- `apps/studio/src/types.ts`
- `apps/studio/package.json`
- `apps/studio/package-lock.json`

Bridge, page/e2e, responsive CSS, and repository documentation changes remain parent-owned.

## Implementation

The live boundary now compiles and applies the repository's Draft 2020-12 schemas with Ajv for:

- `ATLAS_STUDIO_MISSION_CONTROL_V1`
- embedded `ATLAS_STUDIO_SNAPSHOT_V1`
- embedded `ATLAS_GLOBAL_CONTROL_VIEW_V1`
- embedded `ATLAS_COORDINATION_TELEMETRY_V1`
- embedded `ATLAS_EFFICIENCY_METRICS_V1`
- A0/A1 `ATLAS_STUDIO_EVENT_V1` observation events

After structural validation, the adapter applies the existing A1/A0 semantic checks rather than deriving new coordination truth: every supplied honesty flag at the A1, A0, nested control-view, telemetry, metrics, and event boundaries must be strictly `true`; authority-bearing attention flags are rejected; A0 `OK` cannot wrap `DEGRADED` or `UNKNOWN` panels; and `HEALTHY` requires source `LIVE`, known seal/evidence views, and no `AGENT_MATRIX_MISMATCH`. Unsupported nested schemas fail closed.

The generated adapter fixture was produced by `tests/unit/test_atlas_studio_a1_mission_control.py::build_mc` with the repository's `injected_matrix`. A byte comparison against a fresh builder invocation passed before handoff. This avoids using the intentionally incomplete design fixture as an operational contract packet.

Freshness now has two explicit layers. Source fields in `projection.freshness` and all source timestamps remain unchanged. `source.localFreshness` records `LOCAL AGE CHECK`, receipt/check time, locally computed age from the source-supplied `generated_at_utc`, and an effective local state. A source `LIVE` packet becomes locally `STALE` only when local age exceeds its source-supplied `max_age_seconds`. Receipt time is taken after the response body validates, so bridge latency is included. The hook recomputes once per second while a live projection remains selected.

Request lifecycle changes:

- frontend timeout is 25 seconds, coordinated with the parent's bounded 20-second server contract;
- refresh clears the prior operational envelope before fetching and leaves an unavailable envelope after failure;
- selecting fixture or projection aborts the active request and invalidates its result token;
- unmount aborts the active request;
- late responses cannot replace the selected source even if a fetch implementation ignores abort;
- fixture refresh never calls the bridge and uses only the explicit design fixture envelope.

Dependencies added: runtime `ajv`; dev `@testing-library/react`, `jsdom`, and parent-requested `@axe-core/playwright`.

## Test-first evidence

Initial focused run exposed the intended old-behavior failures: malformed A0/control/telemetry and nested dishonesty were accepted; local expiry was ignored; and source switch/unmount did not abort. Two timer tests first exposed a harness-order error, which was corrected. The 25-second regression was then mutation-checked by restoring the old 4-second cap: it failed at the 24,999 ms assertion, and passed again after restoring 25 seconds. A later response-time test failed with local age `0` instead of `5`, then passed after moving the default local timestamp to response receipt.

Fresh verification:

```text
npm run check
  typecheck: exit 0
  vitest: 4 files, 31 tests passed
  vite build: exit 0
```

The focused adapter suite passed 13/13 and the hook suite passed 6/6 within that final run.

## Review notes and limits

- Canonical schemas intentionally allow documented extension properties at several projection layers; the adapter preserves that compatibility and rejects unknown nested schema identifiers where the frontend explicitly supports a nested body.
- Design fixture and local unavailable envelopes are deliberately not claimed as validated operational A1 packets. Their placeholder `studio_snapshot` shapes remain isolated by `source.kind`.
- The projection can retain source-supplied `freshness.state=LIVE` after the separate local state becomes `STALE`; consumers should display `source.localFreshness.state` for current UI freshness while preserving the source field as evidence. Parent reported updating the projection page accordingly.
- Ajv increases the browser bundle, but it removes hand-maintained structural duplication and keeps the accepted frontend contract tied to the repository schemas.
- No subagent review was run because the task brief explicitly prohibited subagents. Parent owns final whole-candidate review and browser acceptance.
