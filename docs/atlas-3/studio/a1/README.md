# Atlas Studio A1

Read-only Mission Control (`AS-STUDIO-A1-001`) over A0 Studio snapshots + F12
frontier matrix projection.

| Doc | Role |
|---|---|
| [A1-SCOPE.md](./A1-SCOPE.md) | Scope reconciled from repository truth |
| [A1-FIRST-WORK-PACKAGE.md](./A1-FIRST-WORK-PACKAGE.md) | `AS-STUDIO-A1-001` package + owner O1/O6 |
| [A1-EVIDENCE.md](./A1-EVIDENCE.md) | Lane evidence / validation |
| [FRESHNESS.md](./FRESHNESS.md) | Stale/live/offline contract |

```text
AS_STUDIO_A1_SCOPE = RECONCILED_FROM_REPOSITORY_TRUTH
AS_STUDIO_A1_FIRST_WORK_PACKAGE = READY
AS_STUDIO_A1_IMPLEMENTATION = IMPLEMENTED_IN_LANE
O1 = APPROVED (in-process atlas_dag RO runtime; no atlasd required)
O6 = APPROVED (seal/evidence UNKNOWN allowed; never promote to healthy)
MERGE_AUTHORIZATION = NOT_GRANTED
```

## CLI

```bash
python scripts/atlas-studio.py mission-control --json
python scripts/atlas-studio.py mc --agent <id> --max-age-seconds 120
python scripts/atlas-studio.py mc --watch 5   # rebuild each tick
python scripts/atlas-studio.py doctor --json
```
