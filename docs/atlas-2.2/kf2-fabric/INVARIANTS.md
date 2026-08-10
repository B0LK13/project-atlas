# Knowledge Fabric estate — invariants (PREP)

Status: **PREP ONLY**. These rules freeze the fail-closed posture for
`AS-2.2-KF2-FABRIC-PREP-001` / `AS-2.2-KF2-FABRIC-DEEPEN-PREP-001` fixtures and
future `AS-2.2-KF2-FABRIC-001` work.

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
| AS-KF2-INV-TRUTH-001 | Namespace / entity / relationship / inventory ≠ automatic authority | **KF2 ≠ AUTHORITY** |
| AS-KF2-INV-NO-CROSS-PROMOTE-001 | Fabric never sets `cross_promote: true` | **NO CROSS PROMOTE** |
| AS-2.2-KF2-INV-PROJECT-001 | Estate projection cites ids only; never writes emit trees | **PROJECTION ≠ MUTATION** |
| AS-2.2-KF2-INV-CLAIM-001 | Fabric never invents Core claim conflicts or Layer B subjects | **FABRIC ≠ CLAIM SYNTHESIS** |
| AS-2.2-KF2-INV-FED-001 | Estate KF prep ≠ multi-vault federation join | **KF2 ≠ FED** |
| AS-2.2-KF2-INV-XPROJ-001 | Optional XPROJ id cite on entities ≠ authority elevation | **XPROJ CITE ≠ AUTHORITY** |
| AS-2.2-KF2-INV-RELEASE-001 | Prep fixtures set `atlas_2_1_release_certified = false` | **NO 2.1 RELEASE STAMP** |

## Negative outcomes (expected fail-closed)

| Attempt | Expected error key |
|---|---|
| Cross-promote KF row into Layer B | `kf2-prep-cross-promote-forbidden` |
| Elevate fabric to Layer B authority | `kf2-prep-authority-elevate-forbidden` |
| Projection write under `generated/kf2/` | `kf2-prep-projection-write-forbidden` |

### Deepen forbidden-action vocabulary (`AS-2.2-KF2-FABRIC-DEEPEN-PREP-001`)

| Attempt | Expected error key |
|---|---|
| Authority elevate (deepen card) | `kf2-fabric-authority-elevate-forbidden` |
| Cross-promote (deepen card) | `kf2-fabric-cross-promote-forbidden` |
| Projection write (deepen card) | `kf2-fabric-projection-write-forbidden` |
| Layer B canonical write | `kf2-fabric-layer-b-write-forbidden` |
| Release-cert stamp | `kf2-fabric-release-cert-stamp-forbidden` |
| PILOT invent | `kf2-fabric-pilot-invent-forbidden` |
| LLM authority stamp | `kf2-fabric-llm-authority-forbidden` |
| KF2 runtime mutation | `kf2-fabric-runtime-mutation-forbidden` |

Deepen negatives always set `evidence_class=fixture-only`,
`authentic_estate=false`, `release_certified=false`, `pilot_pass=false`,
`canonical_writes=false`. See `DEEPEN-FIXTURE-PLAN.md`.

## Allowed documentation posture

- Reference AS-KF2-* docs and schemas **conceptually**
- Cite roadmap package `AS-2.2-KF2-FABRIC-001` as the post-unlock production slot
- Keep all new files under `docs/atlas-2.2/kf2-fabric/**` (+ unique unit test)
