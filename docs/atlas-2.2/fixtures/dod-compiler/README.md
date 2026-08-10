# DoD compiler fixtures (PREP)

Status: **PREP ONLY** — review payloads, not a harness.

`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO`

## Policy

- Synthetic IDs only; no host-specific roots
- No secrets / PII / raw provider output
- Fixture PASS ≠ authentic PILOT / release cert
- Do not reference from production code or required CI before unlock

## Files

| File | Role |
|---|---|
| `sample-goal.json` | Goal stub |
| `sample-dod-chain.json` | Complete chain input (FX-2.2-DOD-001) |
| `expected-proof-pass.json` | PASS proof shape |
| `expected-proof-incomplete.json` | Missing evidence → INCOMPLETE |
| `expected-proof-fail-evidence-class.json` | Fixture≠pilot → FAIL |
| `expected-proof-fail-unknown-criterion.json` | Orphan binding → FAIL (FX-2.2-DOD-004) |
