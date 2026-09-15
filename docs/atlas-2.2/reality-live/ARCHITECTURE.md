# Live Reality Gap collectors — architecture (PREP deepen)

Package: **AS-2.2-REALITY-LIVE-DEEPEN-PREP-001**  
Status: **PREP ONLY** — non-normative until 2.2 unlock + contract freeze.

## Problem

Wave-1 PREP (PR #167) defined four evidence planes, collector contracts, and
positive fixture shapes. Sibling wave-2 packages carry explicit invariants,
forbidden-action vocabulary, and negative rehearsal payloads. Live Reality Gap
collectors lacked that sibling depth.

## Design sketch (deepen overlay)

```text
  declared maturity (board / matrix / package cards)
            │
            v
   ┌────────────────────┐
   │ plane collectors   │  read-only per plane
   └─────────┬──────────┘
             v
   ┌────────────────────┐
   │ aggregator         │  derived gap report only
   └─────────┬──────────┘
             v
   reality-live-gap-report (derived)
             │
             └── never writes Layer A/B · never stamps RELEASE / WEB ACCEPTED
```

## Planes (peer to base PREP)

| Plane | Question | May raise maturity alone? |
|---|---|---|
| `conversational` | What did humans/agents say? | **No** — quarantine-class |
| `documentary` | What do docs claim? | **No** — claims only |
| `implementation` | What does code provide? | Partial — with ops corroboration |
| `operational` | What did runtime observe? | Partial — within safety envelope |

Conservative merge: `observed = min_rank(impl, ops)`; conversational never sole
certifier for `LIVE_PRODUCTION`.

## Deepen delta vs base reality-live PREP

| Concern | base (#167) | This deepen |
|---|---|---|
| Gap kinds | Listed in `PLANES.md` | Explicit invariant tables + forbidden-action enum |
| Adversarial cases | §8 sketch in `COLLECTORS-DESIGN.md` | FX IDs + negative fixtures |
| Truth boundaries | Gap report draft const | Forbidden-action schema + ADR |
| Release credit | Explicit non-claims in package card | Reinforced in invariants + negatives |

## Forbidden-action axis (new in deepen)

| Kind | Meaning |
|---|---|
| `pilot_invent` | Attempt to invent estate / PILOT roots |
| `llm_authority_stamp` | Conversational / LLM evidence as Layer B authority |
| `conversational_sole_certifier` | Dialogue-only `LIVE_PRODUCTION` stamp |
| `layer_b_promotion` | Collector or report writes canonical OKF / claims |
| `release_cert_stamp` | Gap report stamps WEB / RELEASE / 2.1 cert |

## Peer boundaries

| Peer | Rule |
|---|---|
| `AS-2.0-REALITY-GAP-001` | Predecessor static inventory — do not dual-own |
| `AS-2.2-REALITY-GAP-PREP-001` | Strategy register under `reality-gap/` — peer only |
| `contracts/reality-live/` | Base schema drafts — no relocation |
| `reality_gap.py` / `reality_gap_ui.py` | 2.0 runtime — **do not mutate** in PREP |

## Truth boundary (const)

```text
REALITY-LIVE GAP REPORT ≠ PILOT PASS / ≠ WEB ACCEPTED / ≠ RELEASE CERT / ≠ Layer B
```

## Certification wall

| Field | Const / rule |
|---|---|
| `pilot_roots` | `0` |
| `authentic_estate` | `false` on fixtures |
| `evidence_class` | `fixture-only` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |
