# AS-2.2 ADV pool — threat matrix sketch (PREP)

Status: **PREP ONLY**. Rows are design-intent adversarial expectations for
2.2 prep surfaces. They are **not** executable live ADV suite entries and
**must not** be folded into `docs/atlas-2.1/ADV-LIVE-SUITE.md` until a
post-unlock 2.2 ADV package explicitly owns that promotion.

Flags (explicit):

- `ATLAS_2_1_RELEASE_CERTIFIED = NO`
- `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO`
- Authentic PILOT / SYNC-AUTH / TWIN-AUTH / RELEASE certification: **not claimed**

## Cross-cutting invariants (all surfaces)

| ID | Assertion |
|---|---|
| ADV-2.2-X-01 | Fail-closed on ambiguous identity, path, or evidence class |
| ADV-2.2-X-02 | Fixtures never embed real secrets; findings are metadata-only (NFR-004) |
| ADV-2.2-X-03 | No authority elevation: retrieval / packs / memory / eval / LLM ≠ Layer B |
| ADV-2.2-X-04 | Fixture PASS ≠ authentic PILOT PASS; evidence classes stay distinct |
| ADV-2.2-X-05 | No wall-clock stamps in generated fixture expected bytes (NFR-001) |
| ADV-2.2-X-06 | Path refs are synthetic relative vault paths; traversal fails closed (AT-013) |
| ADV-2.2-X-07 | Does **not** reopen 2.1 Host/CORS / L3 / ops-receipt ADV (`#154`/`#155`) |

## Surface matrix

### RET — Hybrid Retrieval 2 prep

| ID | Abuse / threat | Fail-closed expectation |
|---|---|---|
| ADV-2.2-RET-01 | Semantic/vector slot enabled without versioned index contract | Reject / slot stays OFF |
| ADV-2.2-RET-02 | Graph / KF rank silently outranks higher-authority lexical hit | Forbidden; lexical/authority precedence preserved |
| ADV-2.2-RET-03 | Retrieval plan writes vault / promotes claims | No write path from retrieval planning |
| ADV-2.2-RET-04 | Unresolved temporal filter invents validity | Return **unknown**, do not invent |
| ADV-2.2-RET-05 | Provider embedding egress / secret in plan receipt | Metadata-only; quarantine provider payloads |

### CTX — Context Compiler prep

| ID | Abuse / threat | Fail-closed expectation |
|---|---|---|
| ADV-2.2-CTX-01 | Context pack stamped as Layer B authority | Pack remains derived / non-authoritative |
| ADV-2.2-CTX-02 | Pack includes quarantined or secret-bearing source body | Strip / redact; metadata-only findings |
| ADV-2.2-CTX-03 | Oversized / unbounded pack growth | Bounded budget; overflow receipt fail-closed |
| ADV-2.2-CTX-04 | LLM rewrite of pack presented as evidence | LLM≠authority; quarantine until validated |
| ADV-2.2-CTX-05 | Profile selects write/promote tools | Deny-by-default; read/compile only |

### MEM — Memory governance prep

| ID | Abuse / threat | Fail-closed expectation |
|---|---|---|
| ADV-2.2-MEM-01 | Session memory promoted to canonical claim without provenance | Reject; memory ≠ Layer B |
| ADV-2.2-MEM-02 | Cross-project memory bleed without identity lock | Fail-closed on ambiguous vault/project identity |
| ADV-2.2-MEM-03 | Retention / tombstone ignored on replay | Replay bound to snapshot + scope; mismatch rejected |
| ADV-2.2-MEM-04 | Secret material retained in durable memory fixture | Forbidden; synthetic tokens only |
| ADV-2.2-MEM-05 | Operator confuses memory hit with verified claim | Explicit evidence-class labels; no silent upgrade |

### KCI — Knowledge CI / eval harness prep

| ID | Abuse / threat | Fail-closed expectation |
|---|---|---|
| ADV-2.2-KCI-01 | Green eval from missing baseline treated as healthy | Unknown≠healthy; absent baseline → fail/unknown |
| ADV-2.2-KCI-02 | Fixture KCI PASS claimed as RELEASE cert | Explicit `release_certified=false` language required |
| ADV-2.2-KCI-03 | Eval mutates vault under test | Harness read-only vs vault under test |
| ADV-2.2-KCI-04 | Flaky / wall-clock dependent scores | Deterministic fixture expectations only |
| ADV-2.2-KCI-05 | LLM judge sole gate for PASS | LLM≠authority; deterministic checks required |

### DoD — Definition-of-Done compiler prep

| ID | Abuse / threat | Fail-closed expectation |
|---|---|---|
| ADV-2.2-DOD-01 | Claim PASS with empty evidence list | Reject / INCOMPLETE |
| ADV-2.2-DOD-02 | Satisfy `authentic_pilot` with `fixture_receipt` | FAIL evidence-class mismatch |
| ADV-2.2-DOD-03 | LLM prose as sole criterion satisfaction | Reject (LLM≠authority) |
| ADV-2.2-DOD-04 | Proof writes Layer B / promote | Forbidden surface |
| ADV-2.2-DOD-05 | Secret material in proof body | Secrets metadata-only; strip |

### TIME — Time Machine / temporal diff prep

| ID | Abuse / threat | Fail-closed expectation |
|---|---|---|
| ADV-2.2-TIME-01 | Diff invents validity windows when unresolved | Return **unknown**; no invented intervals |
| ADV-2.2-TIME-02 | Bitemporal as-of confused with wall-clock now | Explicit as-of binding; no silent “now” |
| ADV-2.2-TIME-03 | Stale winner silently overwrites fresher authority | Conflict / review; no silent authority overwrite |
| ADV-2.2-TIME-04 | Time travel write path into canonical notes | Diff/read only until unlock + authorize |
| ADV-2.2-TIME-05 | Fixture temporal receipt stamped RELEASE | Non-release-blocking; certified flags stay NO |

### REALITY — Reality Live + Reality Gap prep

| ID | Abuse / threat | Fail-closed expectation |
|---|---|---|
| ADV-2.2-REALITY-01 | Reality-gap / reality-live doc mistaken for RELEASE/PILOT cert | Label PREP; flags explicit NO |
| ADV-2.2-REALITY-02 | Gap closed by UI/demo stub evidence | Stub evidence class ≠ authentic estate |
| ADV-2.2-REALITY-03 | Unknown observability rendered healthy | Unknown≠healthy |
| ADV-2.2-REALITY-04 | Gap register rewrite elevates package maturity without evidence | Maturity changes require attributable evidence |
| ADV-2.2-REALITY-05 | Secret paths / absolute host paths in gap fixtures | Synthetic relative paths only |
| ADV-2.2-REALITY-06 | PILOT roots invented to close estate-twin gap | Fail-closed; invent_pilot_roots forbidden |
| ADV-2.2-REALITY-07 | UI plane treated as canonical write surface | UI≠canonical; collectors remain read/report |

### RESEARCH — Research / Ask Atlas 2 prep

| ID | Abuse / threat | Fail-closed expectation |
|---|---|---|
| ADV-2.2-RESEARCH-01 | Empty / oversized research query accepted | Bounds fail-closed (carry Ask Atlas live discipline) |
| ADV-2.2-RESEARCH-02 | Answer presented without provenance citations | Reject / quarantine; no claim without source |
| ADV-2.2-RESEARCH-03 | Provider/tool write capability in research profile | Deny write/promote tools |
| ADV-2.2-RESEARCH-04 | Instruction-bearing source steers research into authority write | Quarantine; prompt-injection boundary (ADR-004) |
| ADV-2.2-RESEARCH-05 | Research receipt claims PILOT or RELEASE | Explicit non-cert; `llm_authority=false` |

## Out of scope (do not reopen)

| Landed 2.1 surface | Owning evidence | Pool action |
|---|---|---|
| API Host / CORS ADV | `#154`, ADV-2.1-17/20 | **Do not rewrite** |
| L3 job-matrix / disable receipts | `#155`, ADV-2.1-11/22 | **Do not rewrite** |
| OPS receipts honesty | `#155`, ADV-2.1-21 | **Do not rewrite** |
| Other ADV-LIVE-SUITE rows 01–22 | `docs/atlas-2.1/ADV-LIVE-SUITE.md` | **Read-only reference** |

## Promotion rule (post-unlock)

A future `AS-2.2-ADV-LIVE-001` (name TBD) may promote selected rows into an
executable suite **after** `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
Until then this file is documentation-only catalog + fixture policy.
