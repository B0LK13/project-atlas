# Agent readiness contract

An adapter is authorized for governed work only when its registry entry matches the operational skill version and SHA-256, is not revoked, and has `rehearsal_status: passed`. A missing, stale, pending, revoked, or **unconfigured** readiness registry is a fail-closed DENY for managed execution (CODEX-SEC-015). Legacy “not-configured ⇒ authorized” is forbidden.

A self-issued session receipt is **evidence only** and is never authority (CODEX-SEC-016). Readiness promotion requires an independently issued, integrity-protected, revocable authority GRANT (`atlas-authority-grant`) whose issuer is distinct from the requesting session agent (CODEX-SEC-019: REQUEST ≠ GRANT ≠ AUTHORIZATION ≠ EXECUTION). Hashing attacker-controlled JSON is not an integrity mechanism.

Read-only advisory agents may be listed as not-applicable and cannot own a completion receipt.
