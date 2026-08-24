# D-162 — PR #423 reconciliation (post-#469 gate open)

```
DIRECTIVE = D-162-SESSION-RECOVERY-PR423-RECONCILE
STALE_PR = 423
STALE_BASE = dc9d81df0ff7106438de44a4bd84df0b955535bc
CURRENT_MAIN = f0e0c979e8ead0fdad4cc51682c560299db0a074
CLASSIFICATION = READY_FOR_FRESH_CARRIER
MERGE_AUTHORIZATION = NOT_GRANTED
```

---

## Semantic delta vs current main

Required behavior (isolation ADV harness):

- evidence-focused isolation ADV
- cross-project leakage probes
- path escape / UNC root / forged project
- secret echo rejection
- lens != authority separation
- UNKNOWN != healthy demotion

On `f0e0c979`: **not landed**. No `test_as_coder_alpha_isolation_adv_001.py` on main.

---

## Stale #423 disposition

Do **not** merge stale tip `efee467` wholesale. Base predates #469/#470 broker/return-gate
landings. CI green on stale base does not certify current-main integration.

---

## Canonical successor

Prep evidence: `D:\atlas-worktrees\d158-prep-423\test_as_coder_alpha_isolation_adv_001.py`

Action: reconstruct one current-main carrier from prep + fresh IV/ADV on exact tip.
Prior #423 branch remains historical reference only.
