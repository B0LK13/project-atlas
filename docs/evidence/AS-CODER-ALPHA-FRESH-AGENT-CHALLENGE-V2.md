# AS-CODER-ALPHA-FRESH-AGENT-CHALLENGE-V2

| Field | Value |
|---|---|
| Package | `AS-CODER-ALPHA-FRESH-AGENT-CHALLENGE-V2` |
| Module | `src/project_atlas/fresh_agent_challenge.py` |
| Tests | `tests/unit/test_as_coder_alpha_fresh_agent_challenge_v2.py` |
| Question | Can a fresh agent receive Atlas Context and understand a project without re-explanation? |
| Scoring | Deterministic library + pytest. No live LLM required for core scoring. |
| Network | Not required |

## Honesty stamps

```
DEMO_FIXTURE != AUTHENTIC_PILOT
MODEL_OUTPUT != AUTHORITY
UNKNOWN != HEALTHY
UI != CANONICAL TRUTH
CODEX_VALIDATED = NO
ATLAS_OPT_WAKE_GATE = CLOSED
```

## What this package is

A reproducible **machine-scored harness** that:

1. Builds a structured context pack from a controlled multi-project fixture
   (`tests/fixtures/demo/estate`: `harbor-api`, `harbor-ops`, `harbor-portal`).
2. Extracts pack-only answers with a deterministic extractor (no model, no
   prompt tricks).
3. Scores those answers against a **separate** expected-answer catalog derived
   from canonical fixture evidence.
4. Optionally adapts a generated Atlas agent-context export for **self-dogfood
   of this repository**, labeled `SELF_DOGFOOD_DEMO` /
   `DEMO_FIXTURE != AUTHENTIC_PILOT`.

The generated pack is evidence, not a benchmark key. Scoring rubrics
(`required_tokens`, `forbidden_tokens`, `leak_tokens`, `unknown_required`) live
only in the catalog and must never appear inside the pack.

## Required question slots

| Slot | Fresh-agent question |
|---|---|
| `identity` | What is this project? |
| `current_state` | What is the current state? |
| `what_changed` | What changed? |
| `governing_decisions` | Which decisions currently govern? |
| `unknown_conflict` | What is unknown or conflicting? |
| `attention` | What requires attention? |
| `source_health` | What is source health? |
| `what_next` | What should be done next? |
| `supporting_evidence` | What evidence supports the answers? |

## Metrics

| Metric | Meaning |
|---|---|
| `CONTEXT_COVERAGE` | Fraction of required slots that have pack evidence (UNKNOWN counts as covered when UNKNOWN is the honest state) |
| `CONTEXT_ACCURACY` | Fraction of slots matching the fixture catalog |
| `STALE_CONTEXT_RATE` | Fraction of slots that treat superseded/forbidden evidence as current |
| `UNKNOWN_HONESTY` | When the catalog requires UNKNOWN, the answer must stay UNKNOWN |
| `CROSS_PROJECT_LEAK_COUNT` | Count of other-project tokens appearing in this project's answers |

## Safeguards

- Expected answers come from harbor-* fixture files (ADR status, datastore
  pins, inventory UNKNOWN table), not model preference.
- UNKNOWN scores correct when evidence is absent (`harbor-portal` change
  history; `harbor-ops` pager/SLO/RPO/region).
- `ADR-002` (superseded MySQL) must not score as governing; `ADR-001` does.
- Hidden benchmark keys inside a generated pack fail closed.
- No model-specific prompt fields (`system prompt`, temperature, vendor names).
- Core scoring does not open a network socket.

## Non-claims

- This harness is not AUTHENTIC_PILOT and not a live-agent exam.
- Self-dogfood of the Atlas repo is still `DEMO_FIXTURE != AUTHENTIC_PILOT`.
- Receipts under `generated/ops/fresh-agent/` are ops telemetry, not Truth Core.
