# DoD compiler — ADV threat rows (docs-only PREP)

Status: **PREP**. Not merged into live ADV suites until 2.2 unlock.

| Threat ID | Abuse | Fail-closed expectation |
|---|---|---|
| T-2.2-DOD-001 | Claim PASS with empty evidence list | Reject / INCOMPLETE |
| T-2.2-DOD-002 | Satisfy `authentic_pilot` with `fixture_receipt` | FAIL class mismatch |
| T-2.2-DOD-003 | LLM prose as sole criterion satisfaction | Reject (LLM≠authority) |
| T-2.2-DOD-004 | Proof writes Layer B / promote | Forbidden surface |
| T-2.2-DOD-005 | Path traversal in evidence path refs | Reject unsafe paths |
| T-2.2-DOD-006 | Embed secret material in proof body | Secrets metadata-only; strip |
| T-2.2-DOD-007 | Wall-clock / nondeterministic proof bytes | Reject / normalize |
| T-2.2-DOD-008 | Reuse 2.0 fixture waiver as 2.1/2.2 pilot proof | FAIL evidence class |

## Relation to 2.1 ADV

These rows must not reopen Host/CORS / L3 matrices already drained on 2.1 tip.
They are additive future ADV catalog entries only.
