# Mission Control freshness contract (A1)

```text
STALE_UI_STATE != CURRENT_TRUTH
NO_DURABLE_CACHE_AS_TRUTH
REBUILD_EACH_INVOCATION
```

## Fields (`freshness`)

| Field | Meaning |
|---|---|
| `generated_at_utc` | Clock at rebuild |
| `snapshot_fingerprint` | Canonical MC fingerprint for this rebuild |
| `max_age_seconds` | TTL (default 120) |
| `age_seconds` | `now - generated_at` (null if unknown/offline) |
| `state` | `LIVE` \| `STALE` \| `OFFLINE` \| `UNKNOWN` |

## Rules

1. Every `mission-control` / `mc` invocation **rebuilds** from builders or
   injected packets. Prior frames are never treated as `LIVE` without rebuild.
2. `age_seconds > max_age_seconds` ⇒ `state=STALE` ⇒ `mission_status=STALE`.
3. Live GitHub client failure ⇒ `state=OFFLINE` (honest; not HEALTHY).
4. `--watch` loops sleep then rebuild; they do not refresh badges from a cache.
5. Freshness is a **projection** of wall-clock age of the MC packet — not
   authority over coordination truth.

See `A1-EVIDENCE.md` and `mission_control.compute_freshness`.
