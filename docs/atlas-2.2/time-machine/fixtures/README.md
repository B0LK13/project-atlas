# Fixture family — time-machine

Synthetic as-of + T1–T2 diff samples for AS-2.2-TIME-MACHINE-001 PREP.
Aligned with AS-2.0-TEMPORAL-001 fail-closed as-of semantics.

| File | Scenario | Notes |
|---|---|---|
| `as-of-selected.sample.json` | FX-2.2-TM-001 | Single-cover selected |
| `as-of-overlap.expect.json` | FX-2.2-TM-002 | Overlap → unresolved |
| `diff-t1-t2.sample.json` | FX-2.2-TM-003 | Full knowledge-diff envelope |
| `claim-diff.sample.json` | FX-2.2-TM-004 | Claim delta block |
| `graph-diff.sample.json` | FX-2.2-TM-005 | Graph≠authority |
| `decision-diff.sample.json` | FX-2.2-TM-006 | Disposition transition |
| `rejected-wall-clock.expect.json` | FX-2.2-TM-007 | `now` rejected |

**Gate credit: NO.** Runner: absent until post-unlock harness.
**PILOT roots: 0.** Evidence class: fixture-only.
