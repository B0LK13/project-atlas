# Atlas Studio coherent workspace handoff

Date: 2026-09-10

This handoff preserves the accepted page-purpose candidate and records the
smallest supported continuation increment.

## Frozen candidate and delivery state

- Accepted candidate tag: `atlas-studio-page-purpose-003`
- Accepted candidate commit: `664325fc539ebbca73254084f56d0edd62c38848`
- Accepted candidate tree: `ca925adddf2128dc4a0f2d636c9622b25ee651c3`
- Continuation UI HEAD: `87d19776907bf6fe76442593df03e06cc3ba31fb` (tree recorded by git at build time)
- Working branch: `feat/atlas-native-daily-workspace-001`
- Remote: `origin https://github.com/B0LK13/project-atlas.git`
- Remote branch: `origin/feat/atlas-native-daily-workspace-001` at `1628017c682986292ffe5fef2bc3767fc5a97db6` (pushed for durable review).
- PR: no PR was returned for this branch by `gh pr list`.
- Final-head CI: no GitHub Actions run is currently listed for this branch; no final-head CI success is claimed here.
- Local Studio validation: `npm run check` passed (44 unit tests, typecheck, production build).

The frozen native artifacts associated with the accepted candidate remain
durable in the candidate evidence directory:

- executable SHA-256: `025a932ef9a03e6ddc739836bf511b28d67fb24b3efc8bfa4bd1d9507df96c0b`
- Debian package SHA-256: `3ff6d51b58929e9596418e99796063adb3b0af50f59c38cec87fd8504f32ee54`
- Continuation executable SHA-256 after the context-strip rebuild: `95128e7c962ff1fa989d3fd9883296de1e15380168c6ceb5bdfd7c371201387a`
- Restart-persistence rebuild executable SHA-256: `6ade9a9d25a4b3a546564a41ce2babce349e3869c117249d19d118a087be325f`
- screenshots: `docs/atlas-3/studio/desktop/evidence/page-purpose-003-before.png` and `page-purpose-003-after.png`

Reproducible build: `cd apps/studio && npm ci && npm run check`; native packaging
uses the repository's Tauri packaging command documented in the candidate
validation record. The accepted candidate is tagged before this continuation
work; no merge or self-IV is implied.

## Validation scope

Native AT-SPI exercised Mission Control, Agents, and Work Graph, including the
read-only disconnected projection state. Browser tests exercised Projects,
Agents, Work Graph, Repository, Verification, Knowledge, Chronicle, Environment,
Design Lab, and Mission Control. Controlled browser checks covered large queues,
keyboard focus, selection, browser-back, reload/refresh persistence, selected
record disappearance, responsive widths, and axe checks.

The authenticated real-data browser test remains skipped unless
`STUDIO_REAL_ACCEPTANCE=1` is supplied. The skipped behavior is the real
authenticated A1 HTTP projection and its candidate counts at the 1366px review
viewport; fixture behavior does not verify that upstream path.

## Supported contract reconciliation

| Capability | Classification | Source contract and owner | Smallest useful connection | Acceptance evidence |
|---|---|---|---|---|
| Mission catalog | Missing field/contract | A1 Mission Control projection; integration owner | Add an explicit catalog/selected-mission record to the integration-owned journey packet; do not infer one from the current snapshot | Schema-valid packet containing catalog state, or explicit unavailable state |
| Dependency data | Available in unmerged candidate | `atlas_studio.task_context` / `atlas_dag` frontier and stack builders; integration/DAG owner | Compose frontier matrix and stack records into Task Context, including dependencies and blockers | Task Context schema validation with a selected lane's dependency records |
| Candidate verification | Available in unmerged candidate, not consumed by bridge | `atlas_studio.action_evidence` and candidate evidence schemas; lifecycle/integration owners | Expose a bounded read-only evidence projection keyed by explicit lane/decision identity | Evidence packet distinguishes CI, IV, authorization, and mutation outcome |
| Knowledge | Available and compatible for journey packets; selected-lane enrichment is blocked by missing vault binding | `atlas_studio.mission_journey` and `task_context` knowledge lenses; integration/project_atlas owner | Pass the authorized project/vault binding when supplied; preserve `UNAVAILABLE` otherwise | Source paths, decisions, freshness, and provenance appear or limitation is explicit |
| History | Available in unmerged candidate for session/continuity records; no event-history feed in current bridge | `mission_session`, `intent_continuity`, and `action_evidence`; lifecycle owner | Add bounded read-only session/continuity/evidence projection over explicit records; never synthesize events | Chronological records retain occurrence/observation timestamps and source refs |

The integration branch `integration/atlas-one-workflow-20260910` contains the
contract implementations above (including `task_context.py`,
`action_evidence.py`, `intent_continuity.py`, `mission_session.py`, and their
schemas), but it is not silently merged into this UI lane. The current bridge
intentionally exposes only Mission Control, Mission Journey, and bounded Task
Context; its live Task Context reports `NO_FRONTIER_MATRIX`, `NO_STACKS`, and
`NO_VAULT_BOUND` when those inputs are not supplied.

## Continuation increment

Mission Control now selects the first source-ordered attention record for
inspection without implying priority. Group headings name source causes (for
example, “Owner decisions”) and retain access to every record. When a user
follows a supported detail route, the selected attention identity is carried in
local presentation storage, bound to the current repository, and shown as a
compact context strip with a return route to the decision queue. On reopening,
the selection is read only after the refreshed projection is loaded; a changed
repository or disappeared record clears it explicitly. This state cannot
execute, acknowledge, or retry work.

## Documentation status

`ATLAS-DOC-RECEIPT: NOT_ISSUED`. The governed documentation synchronization
attempt was blocked by the recorded HTTP 400 insufficient Anthropic API credits.
Raw work and validation evidence remain preserved in git and the candidate
records; no canonical receipt is invented. Retry only after the credit or
supported synchronization prerequisite changes.
