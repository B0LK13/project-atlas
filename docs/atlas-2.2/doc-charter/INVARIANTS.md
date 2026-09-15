# Charter + maturity matrix — invariants (PREP)

Status: **PREP ONLY**. These rules freeze the fail-closed posture for
`AS-2.2-DOC-CHARTER-PREP-001` fixtures and future `AS-2.2-DOC-CHARTER-001` work.

## Certification posture

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO
```

Unlock remains `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` after
`v2.1.0`. Fixture rehearsal under this tree grants **no** WEB / RELEASE /
PILOT credit.

## Hard invariants

| ID | Rule | Shorthand |
|---|---|---|
| AS-DOC-CHARTER-INV-TRUTH-001 | PREP matrix draft ≠ release certification | **PREP ≠ CERT** |
| AS-DOC-CHARTER-INV-RELEASE-001 | Prep fixtures set `atlas_2_1_release_certified = false` | **NO 2.1 RELEASE STAMP** |
| AS-DOC-CHARTER-INV-UNLOCK-001 | Prep fixtures set `atlas_2_2_intelligence_unlocked = false` | **NO 2.2 UNLOCK STAMP** |
| AS-DOC-CHARTER-INV-PILOT-001 | No PILOT root invent on prep fixtures | **NO PILOT INVENT** |
| AS-DOC-CHARTER-INV-RUNTIME-001 | No mutation of Core intelligence modules on this tip | **NO RUNTIME MUTATION** |
| AS-DOC-CHARTER-INV-UI-001 | UI / Graph / LLM never canonical | **UI≠CANONICAL / LLM≠AUTHORITY** |
| AS-DOC-CHARTER-INV-UNKNOWN-001 | Unknown evidence never maps to healthy | **UNKNOWN≠HEALTHY** |

## Negative outcomes (expected fail-closed)

| Attempt | Expected error key |
|---|---|
| Set `atlas_2_1_release_certified: true` on prep tip | `doc-charter-prep-release-certified-forbidden` |
| Invent PILOT roots to justify matrix rows | `doc-charter-prep-pilot-invent-forbidden` |
| Promote PREP matrix to `v2.2.0` cert language | `doc-charter-prep-matrix-cert-forbidden` |

## Allowed documentation posture

- Reference 2.1 charter + matrix **conceptually**
- Cite roadmap package `AS-2.2-DOC-CHARTER-001` as the post-unlock production slot
- Deepen `docs/atlas-2.2/CHARTER.md` with goals, vocabulary, and DAG summary
- Keep new package files under `docs/atlas-2.2/doc-charter/**` (+ unique unit test)
- Do **not** edit `docs/atlas-2.2/README.md`
