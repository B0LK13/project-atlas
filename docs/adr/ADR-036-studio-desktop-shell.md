# ADR-036 — Linux read-only Studio desktop shell

Status: proposed; committed review candidate, not released.
Date: 2026-09-09
Mission: M-CODEX-ATLAS-STUDIO-LINUX-VISUAL-SHELL-001

ADR-035 is occupied by upstream governed action intent. The current A1 ADR
directory ends at 035; 036 was checked against the fetched A1 base and main during D-005 recovery.

Use Tauri 2 for native window lifecycle and React with TypeScript for presentation.
React reuses repository frontend experience and supports the existing component
and testing ecosystem. Svelte would offer compact components but introduce another
frontend convention without an identified benefit for this shell.

The Python development adapter calls the existing A1 structured builder.
It exposes fixed read-only HTTP routes, not shell execution or a new truth engine.
Rust registers no application invoke commands and installs no shell/filesystem plugin.
The packaged executable requires a separately running read adapter for real data.
It does not contain or start a daemon.

Three retained prototypes explore spatial orbital control, a dense evidence
workbench, and a temporal living project twin. The temporal direction is selected
for readable relationships between work and evidence, with workbench density.
This is product judgment, not a measured trust score.

Real mode displays only supplied A1 fields. Rich agent cards, graph topology,
knowledge cards, repository file detail and narrative history remain previews.
Loading, disconnected and projection errors have separate presentation labels; missing operational fields remain unavailable. Fixture mode requires explicit selection.
Presentation settings and navigation cannot grant authority.

No A2 implementation, independent verification, release or merge is claimed.

Current recovery and acceptance evidence: [RECOVERY-005](../atlas-3/studio/desktop/RECOVERY-005.md).
