# ATLAS-STUDIO-QUOTA-EFFICIENT-DAILY-OPERATION-011

Commit: `ef7335c3892b230abe8f6f02d1aa557c058ee824` plus the cache changes in the following checkpoint.

Reliability checkpoint: `732d8f520cbccf10877e1515db98b95fefe3c285` / tree `1819111f`. The rebuilt native executable remains the preserved `ef7335c3` binary because application build inputs did not change; the bridge revision changed.

The preserved trace measured 238 upstream reads per cold projection: 1 authentication, 1 PR list, and 236 repository/event/PR detail reads. The bridge previously repeated that collection for every route request and concurrent client. The Studio bridge now coalesces equivalent in-flight collections and caches a validated packet for 15 seconds, keyed by repository and agent. Route changes, Mission Journey, Task Context, and local filtering reuse the packet; source-generated timestamps are unchanged.

Measured boundary behavior:

| Scenario | Reads | Result |
|---|---:|---|
| Cold key | 238 | Full source coverage collected |
| Warm same key within 15s | 0 | Same validated packet, original source time |
| Three equivalent concurrent callers | 238 total | One builder, three consumers |
| Different repository key | 238 | Isolated collection |
| Expired key | 238 | Fresh collection |
| Failed build | 0 cached | Equivalent calls suppressed for 5 seconds, then retry |

Controlled tests are in `apps/studio/bridge/test_projection_cache.py`. They cover concurrent coalescing, expiry, repository isolation, and failed-build non-caching. The native real-data acceptance command remains:

```bash
tauri-driver --native-driver /usr/bin/WebKitWebDriver --port 4444
STUDIO_NATIVE_SOURCE=real STUDIO_NATIVE_MANAGE_BRIDGE=1 npm run native:acceptance
```

The 503 reproduction remains an upstream GitHub API rate-limit condition, not a source-coverage reduction. No credentials are cached. CI, IV, merge, and documentation synchronization retain their independent status; the documentation vault remains blocked with 27 raw events and no canonical receipt.

The native harness was rerun against the new bridge revision (WebDriver session `38d420f1-5dd5-43d9-9505-b8eec3d28a3b`): real Mission Control selection/detail, Verification navigation and return, keyboard focus, isolated disconnect, restart recovery, and screenshot all passed.

## Review handoff

`gh` is invoked through the existing `RequestClient` subprocess boundary. The preserved rate-limit trace contained only the CLI error category (`API rate limit exceeded`); no `Retry-After`, reset epoch, or response headers are requested or exposed by the current commands. The five-second boundary is therefore duplicate-failure suppression, not quota-aware recovery. A collector contract that returns a sanitized reset time or retry delay is required before Studio can honor upstream guidance.

The native harness covers both cold failure (the unavailable projection state with no valid snapshot) and failure after a successful load (owned bridge stop followed by refresh). The latter clears operational data and shows `Projection unavailable`; it does not display expired data as current. Recovery reloads usable controls. Stale-source labeling remains covered by the separate fixture campaign.

Cache keys are `(repository, agent_id, GH_HOST)`. Task Context's lane is applied after the shared Mission Control packet and does not alter that packet's collection. The bridge process assumes its access environment is fixed for its lifetime; restart it after changing credentials or other `gh` configuration. Credential values are never stored in the key or cache.

Collector handoff: the 238-read cold trace breaks down as 1 authentication call, 1 open-PR listing, 2 repository/default-branch and branch-head reads, 1 DAG issue listing, 2 DAG issue detail reads (body and comments), and 231 per-PR/detail API reads (commits, workflow runs, review comments, and ancestry comparisons). The dominant fan-out is per-PR detail and ancestry work. The owning collector is `scripts/atlas_dag/gh.py` plus `apps/studio/bridge/projection_worker.py`; proposed upstream work is to batch or incrementally reuse unchanged commit/run/review/ancestry records while preserving pagination, complete PR coverage, repository/agent identity, and source-generated freshness. Studio's bounded cache and failure boundary are the smallest changes available in this lane.

These are invocation counts, not a claim that every command consumes an identical GitHub quota unit; the underlying REST and GraphQL/rate-limit accounting remains an upstream GitHub concern.
