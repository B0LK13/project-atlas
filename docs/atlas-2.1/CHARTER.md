# Atlas 2.1 — Charter

## Non-goals

- Reopening or rewriting `v2.0.0` tag, freeze tip, receipts, or final-cert waiver history
- Claiming authentic estate PILOT from fixtures
- Elevating Graph / KF2 / FED / PROV to Layer B authority
- Unsupervised live writes to protected vault planes

## Goals

1. Live HTTP API over a shared application service layer
2. Web shell consuming live vault data (not sample JSON stubs)
3. Read-first MCP server bound to allow-listed tools
4. Real OpenAI export import path (file export → quarantine → optional promote gates)
5. Supervised live scheduler (operator-armed; receipt-gated)
6. Bounded L3 autonomy (enabled only under AUTHZ + receipts)
7. Authentic estate PILOT PASS as a release gate

## Maturity vocabulary (normative for audit)

| Class | Meaning |
|---|---|
| `LIVE_PRODUCTION` | Operates on real vault/estate inputs with operator controls |
| `LIVE_READ_ONLY` | Live reads only; no mutation path |
| `BOUNDED` | Live or near-live with hard safety envelopes |
| `CONTRACT_ONLY` | Schema/registry/envelope without runtime service |
| `FIXTURE_ONLY` | Synthetic fixtures only |
| `PROTOTYPE` | UI/docs prototype; not production wiring |
| `DRY_RUN` | Plans receipts but forbids live dispatch |
| `DISABLED` | Code path present but fail-closed / off by default |
| `STUB` | Placeholder returning canned structure |
| `DOCUMENTATION_ONLY` | Spec/docs without executable package |
| `SUPERSEDED` | Replaced by a 2.1 package |

## 2.0 boundary

Atlas 2.0 remains RELEASE CERTIFIED under fixture final-cert waiver.
Atlas 2.1 is a **new** release line (`v2.1.0`).
