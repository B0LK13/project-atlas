# PROTOTYPE — Atlas 2.0 contract review walkthrough (NON-PRODUCTION)

Status: **PROTOTYPE / PREP ONLY / NON-PRODUCTION**.
`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

This is a reviewer walkthrough, not an executable contract, payload, schema,
API, CLI design, or evidence receipt. Names below are descriptive prose and are
not reserved production identifiers.

## Walkthrough goal

Exercise the separation between a candidate requirement, a falsifiable
invariant, a reserved fixture scenario, and governor evidence without treating
one as proof of another.

## Example review sequence

1. Select one package stub and one candidate FR from
   `PACKAGE-CONTRACT-STUBS.md`.
2. Identify the actor, input class, observable outcome, rejection outcome, and
   pinned 1.0 dependency.
3. Select one candidate INV and state what observation would falsify it.
4. Link one positive and one negative reserved scenario from `FIXTURE-PLAN.md`.
5. Check related T-2.0 and OQ entries; an unanswered OQ keeps the review open.
6. Record which durable evidence would be required after authorization.
7. Leave every freeze and READY row **NO** unless a governor performs the
   separately governed flip.

## Illustrative trace (not a decision)

| Review element | Illustrative reference | What it cannot prove |
|---|---|---|
| Candidate FR | FR-2.0-SYNC-002 | that conflict semantics are approved |
| Candidate INV | INV-2.0-SYNC-002 | that an executable oracle exists |
| Reserved scenario | FX-2.0-SYNC-001 | that payloads or a runner exist |
| Threat | T-2.0-014 | that mitigation is implemented |
| Open question | OQ-011 | any selected answer |
| Prep baseline | `bfdc5862b46c7e8da8fff26224fac8b7b6a2f59` / `fa404c270c1659d4c48739440a43087a4226b939` | release certification or compatibility freeze |

## Stop conditions

Stop the walkthrough and leave the row **NO** if the review would need to:

- choose an answer to an open question;
- infer authority, acceptance, authorization, or pilot status;
- add machine-readable payloads or production schemas;
- wire a prototype into `src/`, `apps/`, package data, or CI;
- treat branch ancestry as a certified 1.0 snapshot.

This prototype contributes no gate evidence.
`ATLAS_2_0_IMPLEMENTATION_READY = NO`.
