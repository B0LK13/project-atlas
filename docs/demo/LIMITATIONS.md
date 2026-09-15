# Technical Demo — Limitations & Non-Claims

> **DEMO** · **NOT AUTHENTIC PILOT** · **NOT RELEASE EVIDENCE**
>
> `AS-DEMO-2.1-001` · `TECHNICAL_PREVIEW`

## Hard non-claims

1. **Not authentic pilot.** DEMO_FIXTURE success does not wake
   `AS-2.1-PILOT-AUTH-001` and does not set `AUTHENTIC_ESTATE_ROOT`.
2. **Not release evidence.** Do not cite this package for
   `ATLAS_2_1_RELEASE_CERTIFIED` or `v2.1.0` tag authority.
3. **Not production estate sync.** INT-013 / live estate sync against
   unknown roots remains closed.
4. **Not authority elevation.** Conflict demos illustrate fail-closed
   behavior; they do not invent winners or subjective trust scores.
5. **Not a substitute for clean-clone certification.** Hidden machine
   state (orphans caches, prior vaults) must not be required for Mode A.

## Policy: no invented authentic markers

**Forbidden:** writing `.atlas-project.yaml` into real project trees solely
to obtain “authentic” discovery hits for demo or pilot optics.

**Allowed:** markers under committed fixture paths, including:

- `tests/fixtures/demo/estate/**`
- `tests/fixtures/pilots/**`
- other explicit `tests/fixtures/**` corpora

## Capability gaps (honest)

| Area | Limitation |
|---|---|
| Browser E2E | `BROWSER_E2E_MISSING` via isolated package [`browser-e2e/`](browser-e2e/) when harness/tooling blocked |
| Ask Atlas | Answers only as strong as compiled evidence; unknown/conflict are success classes |
| Graph | Projection / navigation aid — not Layer B truth |
| Mode B | Optional; may feed pilot work only if pilot rules pass independently |
| OpenAI / L3 | Optional demo lanes; not required for Mode A Technical Preview |

## Finding policy

Demo failures → `DEMO-FINDING-###` with severity.
CRITICAL/HIGH must clear before **TECHNICAL DEMO — VERIFIED**.

## Relationship to Atlas 2.0 / 2.1

| Line | Status vs this demo |
|---|---|
| Atlas 2.0.0 | Untouched compatibility anchor |
| Atlas 2.1 authentic pilot | Remains dormant / release-critical |
| This Technical Preview | Parallel product-validation lane |

## Operator checklist before audience demos

- [ ] Banner stated (DEMO / NOT AUTHENTIC PILOT / NOT RELEASE EVIDENCE)
- [ ] Corpus path is `tests/fixtures/demo/estate` (or documented Mode B root)
- [ ] Web/API stamps show demo or fixture — not authentic pilot
- [ ] Conflict / unknown prompts behave honestly
- [ ] No claim that v2.1.0 is release-certified from this run
