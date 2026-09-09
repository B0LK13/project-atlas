# Remaining work — mission-session dependability

```text
GOAL_STATUS             = ACTIVE
MERGE_AUTHORIZATION     = NOT_GRANTED
```

## Operational now

- #791 hardening: fingerprint stability, binding fail-closed, conflicting evidence,
  orphan tmp semantics, persistence-failed no-replay, observation UNAVAILABLE.
- Formal IV request packet prepared (owner dispatch only).
- #786 task-context still UNAVAILABLE on this stack.

## Engineering (this lane)

1. Exact-head CI SUCCESS on hardening tip → pin `CI_EXACT_HEAD` / freeze SUBJECT for IV.
2. Corrupt/truncated JSON load paths (if any gap remains after continuity MALFORMED).
3. Load-vs-build TOCTOU: document that session is a point-in-time projection over files
   provided at call time (no live watcher); optional mtime/hash snapshot in provenance.
4. When #786 lands: flip task-context dependency to AVAILABLE without reimplementing.

## Owner actions

- Formal IV dispatch using `iv/A2-006-FORMAL-IV-REQUEST-PACKET.md`
- Merge authorization
- Bugbot usage limits / review tooling (external)
- Stack consolidation / #781 UI
