# AS-STUDIO-A2-001 — first work package (IMPLEMENTED_IN_LANE)

```text
AS_STUDIO_A2_001 = IMPLEMENTED_IN_LANE
IMPLEMENTATION = OWNERSHIP_CLAIM_GOVERNED_PATH
FIRST_GOVERNED_ACTION = OWNERSHIP_CLAIM (eligible unowned/runnable lane)
DISPATCH_STEAL_AUTO = NOT_STARTED
STUDIO_MUTATION_AUTHORITY = NONE (Studio never self-authorizes; emitter decides)
MERGE_AUTHORIZATION = NOT_GRANTED
BUTTON != MUTATION
FORMAL_IV = NOT_STARTED
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

## Implemented flow (AS-STUDIO-A2-001)

```text
MC state (A1)
  → action candidate (F12 OWNERSHIP_CLAIM / unowned runnable)
  → preview / why / impact (RO: blockers, agent bind, fingerprint)
  → policy (capability_claims, freshness, max_age)
  → governed REQUEST (ATLAS_STUDIO_ACTION_INTENT_V1)
  → control plane evaluate (emitter/registry/live ownership)
  → EXECUTE (OWNER_CLAIMED via atlas_dag.emitter) or REFUSE + evidence
```

CLI (preview and execute are separate commands):

```text
atlas-studio claim-candidates [--agent ID] [--json]
atlas-studio claim-preview --agent ID --lane pr/N [--json]
atlas-studio claim-intent --agent ID --lane pr/N   # stdout intent JSON only
atlas-studio claim-evaluate --intent-file PATH [--json]
atlas-studio claim-execute --intent-file PATH [--json] [--dry-run]
```

`claim-execute` always revalidates internally even if evaluate was skipped.

## Exit evidence (lane)

- Denial tests: stale MC fingerprint / max_age, foreign/inactive agent,
  already owned, missing capability, target mismatch, ranking≠authz.
- Idempotency: already-owned-by-self → `REFUSED_IDEMPOTENT_ALREADY_CLAIMED`.
- No Studio self-authorization fields on intents.
- Audit/receipt: intent id + decision + evidence refs.
- A1 honesty preserved: attention still ≠ authorization; MC does not import
  `action_intent`.
- See `A2-EVIDENCE.md`.

## Non-goals for A2-001 (still true)

- Dispatch / IV write / merge / worktree / PTY.
- Steal auto-execute without CLAIM intent.
- UI-only “disabled button” governance.

## Status

```text
SCOPE = READY
IMPLEMENTATION = IMPLEMENTED_IN_LANE
DISPATCH_STEAL_AUTO = NOT_STARTED
FORMAL_IV = NOT_STARTED
MERGE_AUTHORIZATION = NOT_GRANTED
```
