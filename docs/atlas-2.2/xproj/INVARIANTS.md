# Cross-project fabric — invariants (PREP)

Status: **PREP ONLY**. These rules freeze the fail-closed posture for
`AS-2.2-XPROJ-CONTRACT-PREP-001` fixtures and future `AS-2.2-XPROJ-001` work.

## Certification posture

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO
```

Fixture rehearsal under this tree grants **no** WEB / RELEASE / PILOT credit.

## Hard invariants

| ID | Rule | Shorthand |
|---|---|---|
| AS-XPROJ-INV-TRUTH-001 | Registry / edges / indexes / fabric lens ≠ automatic authority | **CROSS-PROJECT ≠ AUTHORITY** |
| AS-XPROJ-INV-NO-FUZZY-001 | No display-name / fuzzy / embedding / LLM identity merge | **NAME ≠ IDENTITY** |
| AS-XPROJ-INV-EXPLICIT-001 | Endpoints / joins / edges exist only via explicit registration | **EXPLICIT ONLY** |
| AS-XPROJ-INV-EDGE-001 | Retained edges must span ≥ 2 projects | **CROSS-PROJECT SPAN** |
| AS-XPROJ-INV-NO-AUTOCOLLAPSE-001 | Duplicate candidates never rewrite UUIDs / skip ingest | **NO AUTOCOLLAPSE** |
| AS-XPROJ-INV-EVIDENCE-001 | Global IDs do not grant cross-project private source reads | **EVIDENCE SCOPED** |
| AS-2.2-XPROJ-INV-RET-001 | Fabric indexes never dual-own `generated/indexes/` | **INDEX ≠ RET-001** |
| AS-2.2-XPROJ-INV-CLAIM-001 | Conflict reports never invent Core claim conflicts | **CONFLICT ≠ CLAIM SYNTHESIS** |
| AS-2.2-XPROJ-INV-RELEASE-001 | Prep fixtures set `atlas_2_1_release_certified = false` | **NO 2.1 RELEASE STAMP** |

## Negative outcomes (expected fail-closed)

| Attempt | Expected error key |
|---|---|
| Fuzzy / name-only join | `xproj-prep-fuzzy-join-forbidden` |
| Autocollapse / UUID rewrite | `xproj-prep-autocollapse-forbidden` |
| Elevate fabric to Layer B authority | `xproj-prep-authority-elevate-forbidden` |

## Allowed documentation posture

- Reference AS-XPROJ-001..004 docs and schemas **conceptually**
- Cite roadmap package `AS-2.2-XPROJ-001` as the post-unlock production slot
- Keep all new files under `docs/atlas-2.2/xproj/**` (+ unique unit test)
