# Prepared PR #346 body (not published until Local D-068 completes)

Do **not** treat this file as live GitHub text until an authorized update.

---

## Package / issue

D-049 / D-062 unlock / D-063–D-067 remediations /
`D-PROJECT-ATLAS-CLOUD-D049-INTEGRATION-069`

## Purpose and scope

Knowledge estate discovery (D-049) after Coder Alpha PASS (D-062), with
identity/bind honesty (D-063), symlink + secret remediations (D-064), and
D-065 HIGH remediations (D-067: `cache/` ignore + depth-bound honesty).

This PR must **not** be merged until Local D-068 returns on exact `ccacaa5`
and Cloud applies the prepared integration lineage (or equivalent) so that
#346 descends from `ccacaa5` with evidence-only commits above it.

Does not start D-042. Does not claim authentic-estate acceptance.

## Candidate lifecycle (do not confuse tip with freeze)

| Candidate | HEAD / TREE | Status |
| --- | --- | --- |
| D-063 | `9c71cc2` / `10539a86` | INVALIDATED by D-064 |
| D-064 | `0509287` / `728f3af` | INVALIDATED by D-065 (`D049_WINDOWS_IV=FAIL`, HIGH=2) |
| D-067 | `ccacaa5` / `d26768` | **CURRENT semantic freeze** (Local D-068 target) |

`#346` branch tip may still be `d3a9458` (D-064 evidence on `0509287`) until
the prepared integration lineage is applied. **Branch tip ≠ semantic freeze.**

Prepared integration (separate branch, #346 ref not moved during D-068):

- strategy: merge D-064 evidence onto `ccacaa5`
- production blobs equal `ccacaa5`
- Local result applicable to integration tip: YES (once D-068 finishes on `ccacaa5`)

## Exact base and source

- Exact base commit: `072f1395ee310a876e93d633264f3ece43cecc3c`
- Semantic freeze (Local): `ccacaa5bcb094f35017c7195264fef55e382cb49`
- Semantic freeze tree: `d26768fe753c888cd45001987da2afe977c79d45`

## Security impact

Estate discovery ignore/depth honesty and git-remote userinfo sanitization
(including quoted git-config URLs). Path/symlink/reparse contracts from D-064
are preserved.

## Documentation impact

Evidence receipts for D-062–D-067. Historical freezes retained; superseded
in later receipts, not rewritten.

## Migration or operational impact

- Migration or operational impact: `none`

## GitHub settings impact

None — settings changes are a separate, later phase.

## Governance state

- `LOCAL_D068_REVALIDATION = IN_PROGRESS`
- `D_049_ACCEPTANCE = NOT_YET_EVALUATED`
- `AUTHENTIC_USER_ESTATE_ACCEPTANCE = NOT_EVALUATED`
- `D_042_EXECUTION_GATE = CLOSED`
- Independent certification: pending Local D-068
- Project Owner integration authorization: not granted

## Merge readiness (Cloud matrix)

- CASE A — Local D-068 PASS on `ccacaa5`/`d26768`, HIGH_OPEN=0, integration
  semantic diff=0, CI green → `READY_FOR_FINAL_MERGE_AUTHORIZATION`
- CASE B — Local FAIL → `REMEDIATION_REQUIRED` (do not treat integration as merge-ready)
- CASE C — Local tested wrong target → `VALIDATION_STALE`

Until Local returns: `D049_CLOUD_RECONCILIATION = WAITING_FOR_LOCAL`
