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
| Failed build | 0 cached | Next call retries normally |

Controlled tests are in `apps/studio/bridge/test_projection_cache.py`. They cover concurrent coalescing, expiry, repository isolation, and failed-build non-caching. The native real-data acceptance command remains:

```bash
tauri-driver --native-driver /usr/bin/WebKitWebDriver --port 4444
STUDIO_NATIVE_SOURCE=real STUDIO_NATIVE_MANAGE_BRIDGE=1 npm run native:acceptance
```

The 503 reproduction remains an upstream GitHub API rate-limit condition, not a source-coverage reduction. No credentials are cached. CI, IV, merge, and documentation synchronization retain their independent status; the documentation vault remains blocked with 27 raw events and no canonical receipt.

The native harness was rerun against the new bridge revision (WebDriver session `38d420f1-5dd5-43d9-9505-b8eec3d28a3b`): real Mission Control selection/detail, Verification navigation and return, keyboard focus, isolated disconnect, restart recovery, and screenshot all passed.
