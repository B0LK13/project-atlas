# A2 — Authority boundary

```text
STUDIO_PRODUCES_INTENTS
ATLAS_CONTROL_PLANE_EVALUATES
STUDIO_NEVER_SELF_AUTHORIZES
BUTTON != MUTATION
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
```

## Roles

| Actor | May | Must not |
|---|---|---|
| Atlas Studio (UI/CLI) | Build RO Mission Control; propose action candidates; emit typed intents; show preview/refusal | Claim authority; execute claim/dispatch/merge; mint receipts; clear `authorization_required` |
| Atlas coordination control plane (`atlas_dag` / future daemon) | Validate freshness, agent bind, capabilities, lane mutex; execute authorized mutations; emit evidence | Treat Studio liveness as authority |
| Human / owner | Bind verifiers; grant merge; resolve OWNER_DECISION | Be replaced by attention ranking |

## Evaluation axes (control plane)

1. **Validity** — schema + required refs present; action_type known.
2. **Authorization** — registry capabilities + policy for action_type.
3. **Freshness** — `source_mc_fingerprint` still current within `max_age`;
   live HEAD/ownership re-check (TOCTOU).
4. **Agent bind** — intent actor matches live agent; no foreign frontier reuse
   (A1 `AGENT_MATRIX_MISMATCH` law carries forward).
5. **Idempotency** — deterministic event ids / already-present outcomes.

## Studio mutation authority

```text
STUDIO_MUTATION_AUTHORITY = NONE
```

Until a control-plane decision record authorizes a specific intent id against
current truth fingerprints, no write proceeds. Absence of a denial is not
authorization.

## Continuity with ADR-034 / A1

- ADR-034: Studio is projection; daemon/coordination is authority.
- A1: attention ≠ authorization; stale ≠ current; unknown ≠ healthy.
- A2: intents are the only Studio→mutation bridge; still not self-authorizing.
