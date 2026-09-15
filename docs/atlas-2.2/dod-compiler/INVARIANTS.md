# DoD compiler — hard invariants (PREP deepen)

Package: **AS-2.2-DOD-DEEPEN-PREP-001**  
Status: **normative for this deepen tree**; runtime enforcement deferred until unlock.

## 1. Proof ≠ Layer B authority

| Signal | Allowed | Forbidden |
|---|---|---|
| Proof receipt | `authority_promoted=false`, `consume_only=true` | Promote to claims / concepts |
| Criterion satisfaction | Bind tests + evidence refs | `_promote` / canonical write |
| Fixture rehearsal | Assert non-authority proof | Stamp Layer B / project authority |

Truth boundary:  
`DoD PROOF ≠ LAYER B AUTHORITY / ≠ ESTATE FACTS / ≠ PILOT`

## 2. Evidence class match

| Criterion class | Allowed evidence | Forbidden |
|---|---|---|
| `authentic_pilot` | Estate pilot report only | `fixture_receipt`, invented digest |
| `release_checklist` | REL package row | Auto-cert from fixture proof alone |
| `unit_test` | pytest / ruff / mypy | Pilot / release cert substitute |

Class mismatch ⇒ **FAIL** with `evidence_class_mismatch`; never downgrade to PASS.

## 3. No invented PASS

| Signal | Allowed | Forbidden |
|---|---|---|
| Missing evidence ref | INCOMPLETE + `missing_evidence` | Silent PASS |
| Absent digest / path | INCOMPLETE | Synthesize evidence bytes |
| Empty binding list | INCOMPLETE / FAIL | Manual waiver on `authentic_pilot` |

Missing link in chain ⇒ **INCOMPLETE or FAIL**; never silent PASS.

## 4. LLM ≠ authority

| Field | Const / rule |
|---|---|
| `authority_promoted` on proof | `false` |
| LLM prose as sole satisfaction | rejected (`llm_authority_stamp`) |
| Subjective confidence / trust | **forbidden** (objective signals only) |

Model-generated "done" text never satisfies a criterion.

## 5. Unknown criterion / binding integrity

| Signal | Allowed | Forbidden |
|---|---|---|
| Test binding | `criterion_id` must exist on DoD | Orphan binding to unknown criterion |
| Proof body | Covers every DoD criterion_id | Omitted criterion with implied PASS |

Orphan binding ⇒ **FAIL** with `unknown_criterion`.

## 6. Certification / unlock wall

| Field | Const / rule |
|---|---|
| `pilot_roots` | `0` on deepen fixtures |
| `authentic_estate` | `false` on fixtures |
| `evidence_class` | `fixture-only` on forbidden-action payloads |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

Fixture DoD rehearsal ≠ authentic estate PILOT PASSED ≠ 2.1 RELEASE
CERTIFIED ≠ 2.2 unlock.
