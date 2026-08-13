# D-049 Wave 1 — Knowledge Estate Discovery (implementation start)

**Directive family:** D-PROJECT-ATLAS-KNOWLEDGE-ESTATE-DISCOVERY-049  
**Capability:** AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001  
**Unlocked by:** D-062 (`CODER_ALPHA_ACCEPTANCE = PASS`)

## Gate

```
D_049_EXECUTION_GATE = OPEN
D_049_STATE = IN_PROGRESS
D_042_EXECUTION_GATE = CLOSED
```

## Wave 1 slices landed

| Lane | Status |
|---|---|
| FILESYSTEM_DISCOVERY | LANDED (`estate_discovery.discover_estate`) |
| PROJECT_FINGERPRINTING | LANDED (match states + fingerprints) |
| MATCH_EXPLAINABILITY | LANDED (`why_matched` / `match_evidence`) |
| PROJECT_ISOLATION | LANDED (no name-only merge; CONFLICTING fail-closed) |
| OBSIDIAN_DISCOVERY | LANDED (detect `.obsidian`; no ingest) |
| IGNORE_POLICY | LANDED (ignore dirs + symlink escape) |
| CLI_DISCOVERY | LANDED (`atlas discover --root` / `review` / `connect`) |
| WEB_DISCOVERY | LANDED (`GET /v1/discovery`, `/discovery` page) |
| INCREMENTAL_FOUNDATION | LANDED (cache sidecar; correctness-first) |

## Invariant

```
DISCOVER != INGEST != TRUST != AUTHORITY
```

## Security boundaries

- Explicit authorized `--root` only (refuse home / filesystem root)
- No symlink / reparse escape descent
- No discovered-code execution / package scripts
- No network discovery / whole-disk surveillance
- Knowledge/Obsidian never auto-ingest via `discover connect`

## Next

- Dogfood on real bounded authorized roots when available
- Acceptance metrics (recall / false match / ambiguous / corrections)
- Keep D-042 closed until D-049 acceptance
