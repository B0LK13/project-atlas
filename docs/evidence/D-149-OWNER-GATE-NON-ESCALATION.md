# D-149 — Owner-gate non-escalation

**Package:** `AS-D149-OWNER-GATE-NON-ESCALATION-001`  
**Base main:** `4e71cce0d1c97f408347e256300a41590da4c352`  
**Base tree:** `e9919f5d04bd1613df7254e3281badcdd7832b86`  
**Merge authorization:** `NOT_GRANTED`

## Invariant

Authentic estate availability may satisfy an `AUTHENTIC_ESTATE_ROOT`
prerequisite. It must not grant owner authority and must not rewrite
unrelated owner gates (`MERGE`, `SECURITY`, `HUMAN`, `OWNER`, `RELEASE`,
`GOVERNOR`, `SIGNOFF`) to `NONE`.

## Pre-remediation (live main)

On merged D-148 (`#443` / `4e71cce`):

- `write_estate_credential()` set `OWNER_CAPABILITY_GRANTED=True`
- `refresh_authentic_o2_node_states()` cleared all dependencies and set
  `OWNER_GATE=NONE` / `READY` for sequential O2 packages
- D-148 runner mutated durable state before closure-integrity validation

Adversarial MERGE replay: `BYPASS=True` (`OWNER_GATE` MERGE → NONE).

## Post-remediation

- Consumable transition: `OWNER_GATE==CREDENTIAL` and dependency
  `AUTHENTIC_ESTATE_ROOT` only
- `OWNER_CAPABILITY_GRANTED=False` even when preflight passes
- Closure integrity is required before mutation; failures restore prior DAG/credential bytes
- Adversarial MERGE replay: `BYPASS=False`

## Tests

`tests/unit/test_d149_owner_gate_non_escalation.py` covers the D-149 matrix
plus D-148 preflight regression.

## Not claimed

- `AUTHENTIC_PILOT=YES` (no authentic estate in this environment)
- Independent verifier ≠ implementer certification
- Merge eligibility
