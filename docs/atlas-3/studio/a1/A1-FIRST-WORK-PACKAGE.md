# AS-STUDIO-A1-001 — first work package (READY)

```text
Package: AS-STUDIO-A1-001
Title: Read-only Mission Control projection over F15 control view
Status: READY (design/outcomes) — IMPLEMENTATION NOT_STARTED
Depends: AS-STUDIO-A0-001 TECHNICALLY_COMPLETE; owner O1 for start gate
MERGE_AUTHORIZATION = NOT_GRANTED
```

## Intent

Make Atlas Studio **genuinely useful** as read-only Mission Control: one
typed projection a human can trust to understand coordination state, without
manual reconstruction and without granting Studio execution authority.

## Outcomes (acceptance-oriented)

An implementation agent may choose CLI, TUI, or thin web/desktop chrome, but
**must** satisfy:

1. **Single Mission Control snapshot** derived from A0
   `ATLAS_STUDIO_SNAPSHOT_V1` (or a strictly additive
   `ATLAS_STUDIO_MISSION_CONTROL_V1` that embeds/extends it — no parallel
   protocol). Prefer additive fields over replacement.
2. **First-class panels** mapped 1:1 from F15 `control_view.panels.*`
   (agents, ownership, stacks, frontier, residuals, telemetry, steal,
   dispatch_gates, evidence_health, postmerge, event_bus, system_honesty)
   plus A0 efficiency/residuals honesty — **reuse builders**, do not fork
   eligibility logic.
3. **Attention surface**: deterministic ranking/list of items needing human
   attention (e.g. owner-gated residuals, `EXTERNAL_IV_GATED`, blocked
   frontier, registry inactive, DEGRADED/UNKNOWN panels). Attention ≠
   authority.
4. **Freshness contract**: every view carries `generated_at_utc`, fingerprint,
   and an explicit stale/unknown/offline policy
   (`STALE_UI_STATE != CURRENT_TRUTH`). Cached UI state must never silently
   present as live truth.
5. **Evidence links**: where panels expose PR/run/receipt identifiers, Mission
   Control must surface them as references (not scraped CLI text).
6. **Crash/reconnect**: Studio process exit does not terminate daemon/agent
   tasks; reconnect rebuilds from live builders/daemon (document + test).
7. **Zero mutation API**: no claim/dispatch/emit/merge/IV/write vault routes
   in Studio A1. Denial tests required.
8. **Tests + evidence**: unit/contract tests for panel mapping, stale honesty,
   mutation absence; exact-object CI on the A1 PR tip; evidence doc with
   commands/results. No self-IV; no fabricated verifier binding.

## Suggested technical route (non-binding)

Preferred smallest path given repo truth:

- Extend `scripts/atlas_studio/` with `mission-control` (or `mc`) command that
  prints/structures F15 panels + attention + freshness.
- Keep JSON schema-validated output as the UI protocol for any later Tauri/
  web shell.
- Optional: read-only HTTP mirror behind existing LIVE_API patterns **only**
  if it remains projection-only and does not create a second control plane.

Reject: subprocess to `atlas-dag` and parse stdout; reimplement frontier/
ownership; ship mutation buttons “disabled in UI only”.

## Risks

| Risk | Mitigation |
|---|---|
| Parallel control plane creep | Import F15/F14/F13 only; schema honesty consts |
| Stale UI treated as truth | Freshness/stale fields + tests |
| Assuming atlasd exists | Honor owner O1; degrade honestly if runtime missing |
| Stacked-base drift (#751 not on main) | Document dependency; do not claim merged |
| Overbuilding Tauri before usefulness | A1.0 projection first; shell ADR separate |

## Explicit non-goals

Tauri productization, A2 mutations, Knowledge/Improvement planes, merge of
coordination stack, formal IV.

## Start gate

```text
IF owner O1 answered (or waived with O1a recorded)
  AND A0 closure stamps remain true
THEN AS-STUDIO-A1-001 implementation may begin
ELSE AS_STUDIO_A1_IMPLEMENTATION = NOT_STARTED
```

## Owner prompt (copyable)

> For A1: do we accept in-process `atlas_dag`/GhClient as interim authoritative
> RO runtime (**O1a**), or require a dedicated `atlasd`/service first (**O1b**)?
> Prefer A1.0 CLI/TUI Mission Control before Tauri (**yes/no**)?
