# Atlas Studio — requirements register (01–60)

Source: GitHub issue
[#746](https://github.com/B0LK13/project-atlas/issues/746)
(`AS-STUDIO-INTAKE-20260908-01`). This is a **canonical docs mirror** of the
issue register, not an authority upgrade and not an implementation claim.

Every row is `PREP` until its phase exit evidence exists.

| Source | Requirement |
|---|---|
| 01 Product vision | Full idea-to-software-and-learning lifecycle; Studio is a projection/control interface, never truth authority. |
| 02 Architectural decision | Desktop/CLI/future web/mobile/automation consume the same daemon primitives; policy and Git authority remain behind the boundary. |
| 03 Desktop stack | Preferred Tauri 2 + Rust native shell + TypeScript; select React or Svelte through an ADR and Linux prototype. Rust supports native integrations, not an assumed core rewrite. |
| 04 Runtime separation | Agent runtime outside Tauri; atlasd exposes DAG, harnesses, router, context, gateways, sandboxes, Git/GitHub, knowledge and telemetry. UI termination must not terminate daemon-owned work. |
| 05 Navigation | Home, Projects, Build, Agents, DAG, Code, Terminals, Tests, CI/IV, Research, Knowledge, Evals, Observatory, Settings. |
| 06 Mission Control | Show active milestone, agents, runnable frontier by action class, highest-value eligible work, owner decisions and verified incidents. |
| 07 Project workspace | Overview, goals, ideas, research, architecture, requirements, roadmap, DAG, agents, repository, tests, CI, verification, knowledge, decisions, history and metrics. |
| 08 Idea workflow | Clarification → research → requirements → architecture → plan → DAG → agents → implementation → verification → merge → documentation → knowledge → improvement. |
| 09 Research workspace | Multi-source research with provenance, uncertainty, contradictions and export into requirements/architecture. |
| 10 Architecture workspace | Compare options, produce ADRs, keep executable DAG lineage, refuse unverified research as authority. |
| 11 Requirements | Structured, sourced, testable requirements with uncertainty and change history. |
| 12 Roadmap / milestones | Explicit gates; no silent scope expansion. |
| 13 DAG / work graph | Visualize and operate Features 1–16 style coordination: ownership, freeze, stacks, residuals, frontier classes. |
| 14 Agents | Multi-agent registry, capabilities, activity, handoffs; no self-authorization. |
| 15 Code workspace | Diffs, blame, navigation; never parse CLI text as protocol. |
| 16 Terminals | Scoped PTYs; crash of Studio ≠ kill daemon tasks. |
| 17 Tests | Local/CI test surfaces with evidence links. |
| 18 CI/IV | Exact-head CI/IV; IV ≠ merge; unbound verifiers stay EXTERNAL_IV_GATED. |
| 19 Git/GitHub | Governed claim/dispatch/PR/merge/postmerge/seal behind daemon authority. |
| 20 Knowledge | Quarantine → normalize → validate → project; human regions preserved. |
| 21 Decisions | Owner-origin decisions only as authority; model paraphrase ≠ owner. |
| 22 Chronicle | Ambient capture with honesty about UNKNOWN. |
| 23 Evals / Observatory | Baselines, holdouts, promotion gates; no automatic Atlas-OPT unlock. |
| 24 Improvement Plane | Governed experiments; shadow/canary/rollback. |
| 25 Telemetry | Efficiency metrics; TELEMETRY ≠ AUTHORITY. |
| 26 Settings / secrets | Secrets isolation; least privilege. |
| 27 AuthN/AuthZ | Explicit boundary; UI cannot escalate. |
| 28 Plugins | Versioned contracts; fail closed. |
| 29 Offline / reconnect | Stale/unknown/offline honest states. |
| 30 Obsidian | Open-in-Obsidian and Markdown projections; preserve protected human content. |
| 31 Multi-project | Portfolio views; federation ≠ authority. |
| 32 Windows/macOS | Later surfaces; Linux-first. |
| 33 Mobile/web | Same daemon contracts. |
| 34 Accessibility | Required for shell. |
| 35 Performance | Bounded context; no arbitrary RAG dumps. |
| 36 Localization | Deferred unless gated. |
| 37 Theming | Non-authoritative chrome. |
| 38 Notifications | Policy-gated; not authority. |
| 39 Search | Evidence-backed retrieval. |
| 40 Command palette | Routes to daemon actions only when authorized. |
| 41 Keyboard | First-class Linux desktop UX. |
| 42 Drag/drop | Non-authoritative unless bound to authorized actions. |
| 43 Undo | Only where daemon supports compensating actions. |
| 44 Audit | Receipts and event stream. |
| 45 Threat model | A0 deliverable; continuous update. |
| 46 Compatibility | Migration policy; no wholesale rewrite. |
| 47 Providers | Model neutrality; provider ≠ architecture. |
| 48 Sandbox | Enforcement for agent work. |
| 49 Cost/budget | Reserve/reconcile; unknown-usage defined. |
| 50 Replay | Observable events only; new run needs authority. |
| 51 Evidence hygiene | Illustrative owner numbers stay UNKNOWN until measured. |
| 52 Research leads | External claims need primary sources before adoption. |
| 53 Reuse map | Exact commit/tree inventory in A0. |
| 54 Phases | A0–A8 with explicit gates. |
| 55 Mission Control A1 | Read-only real daemon data; no mutation endpoints. |
| 56 A2 mutations | Claim/dispatch/handoff/worktree/terminal with denial tests. |
| 57 A3 runtime | ≥2 provider adapters; durable across UI failure. |
| 58 A4 lifecycle | Isolated feature with exact-object CI/IV and seal. |
| 59 A5–A7 planes | Knowledge/research/evals attach without replacing A0/A1 contracts. |
| 60 A8 autonomy | Policy-bound lifecycle; denied unsafe actions proven. |

## Traceability

- Issue body is authoritative for owner wording where this table summarizes.
- Implementation mapping lives in phase docs and future package IDs.
- Do not treat checkbox absence in code as product rejection; treat as undone work.
