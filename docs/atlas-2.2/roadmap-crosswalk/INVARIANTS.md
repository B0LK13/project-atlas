# Roadmap crosswalk — invariants (PREP)

Status: **PREP ONLY**. These rules freeze the fail-closed posture for
`AS-2.2-ROADMAP-CROSSWALK-PREP-001` and deepen package
`AS-2.2-ROADMAP-CROSSWALK-DEEPEN-PREP-001`.

## Certification posture

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO
```

Fixture rehearsal under this tree grants **no** WEB / RELEASE / PILOT / unlock
credit.

## Hard invariants

| ID | Rule | Shorthand |
|---|---|---|
| AS-2.2-CROSSWALK-INV-001 | Mapping rows grant no implementation unlock | **CROSSWALK ≠ UNLOCK** |
| AS-2.2-CROSSWALK-INV-002 | Mapped PREP remains PREP until production package execution | **PREP ≠ PRODUCTION** |
| AS-2.2-CROSSWALK-INV-003 | Docs/fixtures only; never mutate `src/` or `apps/` | **NO RUNTIME MUTATION** |
| AS-2.2-CROSSWALK-INV-004 | Stub rehearsal is not release or PILOT certification | **FIXTURE ≠ CERT** |
| AS-2.2-CROSSWALK-INV-005 | No invented authentic estate / PILOT roots | **NO PILOT INVENT** |
| AS-2.2-CROSSWALK-INV-006 | Prep fixtures keep `release_certified = false` | **NO 2.1 RELEASE STAMP** |

## Negative outcomes (expected fail-closed)

| Attempt | Expected error key |
|---|---|
| Treat crosswalk row as unlock | `crosswalk-unlock-claim-forbidden` |
| Treat mapped slot as production-ready | `crosswalk-production-ready-claim-forbidden` |
| Stamp release certified from mapping | `crosswalk-release-cert-stamp-forbidden` |
| Invent authentic estate / PILOT | `crosswalk-pilot-invent-forbidden` |
| Mutate runtime / apps from crosswalk PREP | `crosswalk-runtime-mutation-forbidden` |
| LLM authority over mapping truth | `crosswalk-llm-authority-forbidden` |
| Relabel fixture rehearsal as certification | `crosswalk-fixture-as-certification-forbidden` |

## Allowed documentation posture

- Reference strategy DAG slots conceptually
- Cite harvest indexes without editing them in this package
- Keep all new deepen files under `docs/atlas-2.2/roadmap-crosswalk/**`
  (+ unique unit test)
