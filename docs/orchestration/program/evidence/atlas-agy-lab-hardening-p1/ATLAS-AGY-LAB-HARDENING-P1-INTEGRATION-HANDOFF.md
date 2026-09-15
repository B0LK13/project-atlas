# ATLAS-AGY-LAB-HARDENING P1 — READY_FOR_INTEGRATION_HANDOFF (definitive)

**Status:** READY_FOR_INTEGRATION_HANDOFF  
**Target:** PR #705 integration owner  
**Base HEAD:** `89e0e044f560536357401a0bcdc9ed2c5e25bf59`  
**Worktree:** `[SOURCE-HOST WORKTREE]` (`supervisor/agy-lab-hardening-p1`, uncommitted)

## Full SHA-256
- `lab.py`: `effb9b64dbdfa5541fde38ff1113695521e9c4f0cab5aab68adf622426ca5e43`
- `test_lab.py`: `fe16dda94393f05c8a3fa093c8117bd3cafeecb4033614126986b92a49946bf7`
- binary patch: `6fe1a7d03f2a330b7fd7f18c3d7324180665d72bb6e97887eb72e1cea22eba66`

## Collect-only (unfiltered artifacts on disk)
- `test_lab.py`: **22** — `ATLAS-AGY-LAB-HARDENING-P1-COLLECT-test_lab.txt`
- `experiments/agents_sdk/tests/`: **28** — `ATLAS-AGY-LAB-HARDENING-P1-COLLECT-agents_sdk.txt`

## Count reconciliation vs cited 30/36
Pytest collect truth is **22/28**. The cited **30/36** matches double-counting the **8** `evals.json` case rows on top of collected nodes (`22+8=30`, `28+8=36`). Those cases are already covered by `test_eval_*` nodes and `test_evals_contract`; they are not extra collected IDs.

Vs PR #705 HEAD baseline (**10/16**): **0 removed/renamed/uncollected**; **+12** P1 boundary tests; no parametrize/skip/xfail changes.

## Independent review binding
- Reviewer: `b9085571-cb98-4b66-ae91-6cb476a2043a`
- Evidence: `ATLAS-AGY-LAB-HARDENING-P1-INDEPENDENT-REVIEW.json`
- Bound to same HEAD + file hashes + patch hash: **yes**
- Verdict: **PASS**

## Detail
See `ATLAS-AGY-LAB-HARDENING-P1-COUNT-RECONCILIATION.json`.

Author agent stops P1 here; continues Prime/t003f capability line.

Updated: 2026-09-15T17:49:08Z
