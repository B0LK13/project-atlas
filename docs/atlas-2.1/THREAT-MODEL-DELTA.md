# Atlas 2.1 — Threat model delta (live surfaces)

Extends `docs/atlas-2.0/THREAT-MODEL.md` for live productionization.

| ID | Threat | Mitigation (2.1) |
|---|---|---|
| T-2.1-01 | Unauthenticated LIVE_API reads leak vault metadata | AUTHZ capability tokens / local bind default |
| T-2.1-02 | Web shell writes canonical planes | Read-only API; UI≠canonical invariant tests |
| T-2.1-03 | MCP tool escalation to vault-write | Deny-by-default; read-first server; allow-list only |
| T-2.1-04 | Real OpenAI export contains secrets | `secrets.scan_text` before persist; quarantine |
| T-2.1-05 | Scheduler live dispatch runaway | Operator arming + receipt + supervised mode |
| T-2.1-06 | L3 autonomy silent promote | AUTHZ + receipt gate; fail-closed |
| T-2.1-07 | Fake authentic PILOT via invented roots | Prep searches registry/known only; escalate if 0 |
| T-2.1-08 | Relabel 2.0 fixture waiver as 2.1 PILOT PASS | Immutable 2.0 docs; separate 2.1 PILOT package |
