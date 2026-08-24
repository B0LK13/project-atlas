# AS-CODER-ALPHA-CROSS-SURFACE-002 — drift honesty across surfaces

**LIVE_MAIN_HEAD:** `4e71cce0d1c97f408347e256300a41590da4c352`  
**Branch:** `cursor/atlas-autonomous-night-cycle-742c`

After `atlas connect` and an on-disk source mutation, brief, overview,
state, and exported agent-context JSON all report `source_drift.status=STALE`
and `honesty.stale_is_current=false`.

```
pytest tests/integration/test_cross_surface_drift_honesty_001.py --no-cov
1 passed
```

Honesty: UI/lens != canonical. Stale must not look current.
