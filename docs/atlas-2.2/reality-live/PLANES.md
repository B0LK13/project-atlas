# Reality Gap planes (normative for AS-2.2-REALITY-LIVE-001)

Four orthogonal evidence planes. Each collector reads one plane; the
aggregator merges plane reports into a single derived gap report.

## Plane taxonomy

| Plane ID | Name | Question | Typical inputs (read-only) |
|---|---|---|---|
| `conversational` | Conversational | What did humans/agents *say* happened? | ChatGPT exports, agent session receipts, Ask Atlas transcripts, collab action notes |
| `documentary` | Documentary | What do governed docs *claim*? | OKF notes, `docs/atlas-2.*/`, package cards, ADRs, charter/matrix |
| `implementation` | Implementation | What does the *code* actually provide? | `src/project_atlas/**`, CLI entrypoints, schemas, unit/integration tests |
| `operational` | Operational | What did *runtime* actually observe? | Ops receipts, ops events, API/MCP/sched/L3 live receipts, health snapshots |

## Maturity vocabulary (reuse 2.1 charter)

Collectors map observed evidence to the same classes as
`docs/atlas-2.1/CHARTER.md`:

`LIVE_PRODUCTION` · `LIVE_READ_ONLY` · `BOUNDED` · `CONTRACT_ONLY` ·
`FIXTURE_ONLY` · `PROTOTYPE` · `DRY_RUN` · `DISABLED` · `STUB` ·
`DOCUMENTATION_ONLY` · `SUPERSEDED` · `ABSENT` · `UNKNOWN`

`UNKNOWN` is healthy when evidence is missing — never invent a healthier class.

## Cross-plane gap kinds

| gap_kind | Meaning |
|---|---|
| `claim-without-evidence` | Documentary/board claim with no supporting plane evidence |
| `evidence-without-claim` | Strong plane evidence not reflected on board/matrix |
| `maturity-overclaim` | Claimed class higher than max supported by evidence |
| `plane-conflict` | Two planes disagree (e.g. docs say LIVE, ops empty) |
| `authority-leak` | Conversational/LLM evidence treated as Layer B authority |
| `pilot-invent` | Attempt to invent estate/PILOT roots (always fail-closed) |

## Plane boundaries

```text
conversational  ──┐
documentary     ──┼──► aggregator ──► reality-live-gap-report (derived)
implementation  ──┤
operational     ──┘
         │
         └── never writes Layer A/B canonical content
```

## Per-plane honesty rules

### Conversational

- Dialogue evidence is **quarantine-class** by default.
- May support `FIXTURE_ONLY` / `BOUNDED` / experimental maturity — never
  `LIVE_PRODUCTION` certification alone.
- Secrets: metadata-only findings; never echo matched secret content.

### Documentary

- Package cards and matrices are **claims**, not proofs.
- Docs that say LIVE without linking operational/implementation anchors
  produce `claim-without-evidence` or `maturity-overclaim`.

### Implementation

- Presence of a module/registry ≠ LIVE service.
- Tests asserting fixtures ≠ authentic estate PILOT.
- Prefer code + schema + CLI surface inventory over docstring marketing.

### Operational

- Empty honest receipts → `UNKNOWN` / empty-ok, not fake healthy.
- Supervised LIVE signals (API host, MCP read, sched arm, L3 disable)
  may raise maturity only within declared safety envelopes.
- Never treat DEMO/FIXTURE mode telemetry as authentic estate.

## Non-goals per plane

- No silent authority promotion across planes
- No merging conversational text into OKF concept bodies
- No inventing `.atlas-project.yaml` for operational PILOT
