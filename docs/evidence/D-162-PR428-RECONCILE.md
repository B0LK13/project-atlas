# D-162 — PR #428 reconciliation (post SHADOW-B-001 closure)

```
DIRECTIVE = D-162-SESSION-RECOVERY-PR428-RECONCILE
STALE_PR = 428
STALE_BASE = 7e797468a2eca37c959920912b1fa264df4be638
CURRENT_MAIN = f0e0c979e8ead0fdad4cc51682c560299db0a074
SHADOW_B_001 = CLOSED
CLASSIFICATION = STILL_REQUIRED — FRESH_CARRIER_REQUIRED
MERGE_AUTHORIZATION = NOT_GRANTED
GITHUB_MERGEABLE = CONFLICTING
```

---

## Gate status

#428 was gated on integrated SHADOW-B-001 closure. Integrated-main proof now PASS
(D-154 matrix + broker + hook contract on `f0e0c979`).

---

## Overlap analysis

Main already landed via #470 / D-147R / D-154:

- `continuation_broker.py` (sdk-runtime path)
- `return_gate.py` stop-hook fail-closed matrix
- `cursor_bridge.py` production stop path

Stale #428 introduces parallel `broker.py` / durable-host surface that **conflicts**
with integrated broker architecture. Partial semantic goals (durable host, worker
lifecycle, lease replay, duplicate dispatch prevention) remain **unlanded**.

---

## Disposition

Do **not** merge stale #428. Derive one current-main canonical carrier reconciling
durable-host/worker-lifecycle delta against landed `continuation_broker` — not a
 wholesale revival of conflicting file layout.
