# Reality Gap prep fixtures (AS-2.2-REALITY-GAP-PREP-001)

Status: **fixture rehearsal only**. Not authentic estate evidence.  
Not CI-gated. Not package-data schemas.

| File | Purpose |
|---|---|
| `inventory.fixture.json` | Positive six-gap prep inventory |
| `negative-unknown-as-healthy.fixture.json` | Documents forbidden unknown→healthy coercion |
| `negative-ui-canonical.fixture.json` | Documents forbidden UI canonical writes |
| `negative-pilot-invent.fixture.json` | Documents forbidden PILOT invent |
| `README.md` | This note |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- `healthy = false` on every scenario (unknown≠healthy)
- Never invent PILOT roots or stamp WEB / RELEASE / 2.1 CERTIFIED

See `../AS-2.2-REALITY-GAP-PREP-001.md` and `docs/AS-2.0-REALITY-GAP-001.md`.
