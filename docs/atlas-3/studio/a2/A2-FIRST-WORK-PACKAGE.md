# AS-STUDIO-A2-001 — first work package (READY / NOT_STARTED)

```text
AS_STUDIO_A2_001 = READY
IMPLEMENTATION = NOT_STARTED
FIRST_GOVERNED_ACTION = OWNERSHIP_CLAIM (eligible unowned/runnable lane)
STUDIO_MUTATION_AUTHORITY = NONE
MERGE_AUTHORIZATION = NOT_GRANTED
BUTTON != MUTATION
```

## Mandatory analysis — claim / dispatch / handoff / steal maturity

Inspected under `scripts/atlas_dag/` on this tip:

| Path | Read-only plan | Execute / write | Risk | Leverage for Studio A2.0 |
|---|---|---|---|---|
| **Claim** via F12 `OWNERSHIP_CLAIM` + F04 `emitter.emit_event(OWNER_CLAIMED)` | Frontier action class + eligibility projection | Race-safe lane mutex on #719 bus; capability-checked | Medium — changes ownership; well-gated | **Highest** — gateway to all owned-lane work |
| **Steal** (`steal.plan_steal` / `execute_steal`) | Ranked unowned WRITE-after-claim candidates | Executes claim through same emitter | Medium+ — policy-specialized claim | High reuse, but is a *policy* over claim, not the primitive |
| **Dispatch** (`dispatch.plan_dispatch` / `execute_dispatch`) | Sibling CI/IV plan; dry-run | Triggers CI workflow + IV_REQUEST | High — external side effects; verifier bind | Needs freeze + ownership already; later A2.x |
| **Handoff** (`handoff.build_handoff`) | Full packet generation; TOCTOU stale | **No delivery** | Low (generation) | Useful preview/export; not first *mutation* |

### Recommendation

**First governed action = OWNERSHIP_CLAIM of an eligible unowned/runnable lane.**

Rationale:

1. **Primitive before policy.** Steal is “safe claim of highest-value unowned
   lane” — valuable, but it should sit *on top of* a governed CLAIM intent,
   not replace it.
2. **Lower blast than dispatch.** Dispatch touches CI runners and IV requests;
   claim only posts ownership on the coordination bus under existing mutex.
3. **Mission Control already surfaces the candidate class.** F12 exposes
   `OWNERSHIP_CLAIM` / steal candidates; A1 projects rankings without
   authorizing them — A2.0 closes the REQUEST path honestly.
4. **Mature fail-closed substrate.** Emitter already denies wrong owner /
   capability; Studio must not bypass it with a button.

Rejected as first action (with evidence):

- **Dispatch first** — requires frozen owned lane; higher external blast;
  `VERIFIER_IDENTITY_UNBOUND` already fail-closed; wrong first UX loop.
- **Handoff first** — generation-only today; teaches preview well but does not
  exercise authorization→execution refusal for mutations.
- **Steal-branded first** — conflates ranking policy with authority; prefer
  CLAIM intent that *may* be filled from steal-plan candidates later.

## Target flow (AS-STUDIO-A2-001)

```text
MC state (A1)
  → action candidate (F12 OWNERSHIP_CLAIM / unowned runnable)
  → preview / why / impact (RO: blockers, agent bind, fingerprint)
  → policy (capability_claims, freshness, max_age)
  → governed REQUEST (ATLAS_STUDIO_ACTION_INTENT_V1)
  → control plane evaluate (emitter/registry/live ownership)
  → EXECUTE (OWNER_CLAIMED) or REFUSE + evidence
```

## Exit evidence (when implemented — not claimed now)

- Denial tests: stale MC fingerprint, foreign agent, inactive agent,
  already owned, missing capability.
- Idempotency: already-present OWNER_CLAIMED.
- No Studio self-authorization fields.
- Audit/receipt: intent id + decision + evidence refs.
- A1 honesty preserved: attention still ≠ authorization.

## Non-goals for A2-001

- Dispatch / IV write / merge / worktree / PTY.
- Steal auto-execute without CLAIM intent.
- UI-only “disabled button” governance.

## Status

```text
SCOPE = READY
IMPLEMENTATION = NOT_STARTED
FORMAL_IV = NOT_STARTED
```
