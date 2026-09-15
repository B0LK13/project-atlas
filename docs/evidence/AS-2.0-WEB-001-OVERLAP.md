# WEB_SURFACE_OVERLAP_REPORT — AS-2.0-WEB-001

Recorded before any Wave 16 edits to shared Web files.

```
ASK = VAULT_WIDE
ASK ?project = DISPLAY_CLIENT_HINT_ONLY
TIME_MACHINE = ACTUAL_PROJECT_BINDING
ROADMAP = ACTUAL_PROJECT_BINDING
INTELLIGENCE = ACTUAL_PROJECT_BINDING (project-scoped views)
PORTFOLIO = explicit cross-project scope
```

## Inspected shared surfaces

| File | Role | Wave 16 plan |
|---|---|---|
| `apps/web/src/App.tsx` | Client routes | Add `/intelligence` only. Preserve all existing 1.x routes. |
| `apps/web/src/components/ProdNav.tsx` | Production nav | Add Intelligence link. Add `/intelligence` to `PROJECT_AWARE_PATHS`. Preserve `?project=` copy only; never `from=`/`to=`. Do not change Ask semantics. |
| `apps/web/src/pages/production/KnowledgePage.tsx` | Knowledge lens | **No edit.** Knowledge keeps its own project fallback. Intelligence must not copy that fallback. |
| `apps/web/src/hooks/useLiveAsk.ts` | Ask live hook | **No edit.** Ask stays vault-wide; query is `q` only. |
| `apps/web/src/hooks/useLiveRoadmap.ts` | Roadmap hook | **No edit.** Pattern to copy: live failure → `dataSource=null`, never `demo_stub`. |
| `apps/web/src/hooks/useLiveTimeMachine.ts` | Time Machine hook | **No edit.** Time Machine remains actual project binding (including its own demo default). |
| `apps/web/src/hooks/useReadStatus.ts` | Shared status | **No edit.** Intelligence may consume it for the project selector only. |
| `apps/web/src/api/liveApi.ts` | Shared client | **No edit.** Reuse `liveApiFetch` / `liveApiDemoOnly`. No new POST. No token-in-URL. |
| `apps/web/src/types.ts` | Shared types | **No edit** unless a non-breaking DataSource reuse is already sufficient. |
| `apps/web/src/styles.css` | Shared chrome | Additive truth-state chips only. |

## Preserved 1.x routes

Projects, Knowledge, Context, Ask, Time Machine, Roadmap, Workspace — plus existing Discovery / Graph / Ops / Command Center / Mission Control / Home / design-lab.

## Binding rules Intelligence must not break

1. Ask remains vault-wide. `?project=` on Ask is a display/client hint only. Do not pass project into `useLiveAsk`.
2. Intelligence project-scoped views require explicit `?project=`. No `harbor-api` default. No first-project fallback.
3. Portfolio view is explicit cross-project (`/v1/portfolio-state`) and may run without a project id.
4. Nav copies `project=` only. Never copies Time Machine `from`/`to`.

## Overlap risk

| Risk | Mitigation |
|---|---|
| Accidental Ask scope change | Do not edit Ask page/hook |
| Knowledge default leaking into Intelligence | New page follows Roadmap explicit-select pattern |
| Demo substitution on live HTTP failure | New hook copies Roadmap catch (`dataSource=null`) |
| Shared client mutation | No `liveApi.ts` edits |
| Duplicate semantic pages | One `/intelligence` area with subviews |
