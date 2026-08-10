# Research workspace — ADV threat rows (docs-only PREP)

Status: **PREP**. Not merged into live ADV suites until 2.2 unlock.

| Threat ID | Abuse | Fail-closed expectation |
|---|---|---|
| T-2.2-RES-001 | Promote hypothesis to Layer B claim winner | Forbidden / reject |
| T-2.2-RES-002 | Silent pick among conflicting evidence | Conflicts must remain visible |
| T-2.2-RES-003 | Answer certainty with empty evidence | INCOMPLETE / UNKNOWN |
| T-2.2-RES-004 | Satisfy `authentic_estate` with `fixture_receipt` | FAIL class mismatch |
| T-2.2-RES-005 | LLM prose as sole ANSWER authority | Reject (LLM≠authority) |
| T-2.2-RES-006 | Canonical write via Ask Atlas 2 path | Forbidden surface |
| T-2.2-RES-007 | Path traversal in evidence path refs | Reject unsafe paths |
| T-2.2-RES-008 | Embed secret material in pack / answer | Secrets metadata-only; strip |
| T-2.2-RES-009 | Wall-clock / nondeterministic pack bytes | Reject / normalize |
| T-2.2-RES-010 | Treat graph projection as authority | `graph_authority=false` enforced |

## Relation to 2.1 ADV

These rows must not reopen Host/CORS / L3 matrices already drained on 2.1 tip.
They are additive future ADV catalog entries only.
