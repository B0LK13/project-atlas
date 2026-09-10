# Atlas Native Daily Workspace

Directive: `ATLAS-NATIVE-DAILY-WORKSPACE-001`

This candidate extends the #781 Linux Atlas Studio surface from integration baseline `2752be76` (which carries the supported one-workflow contracts). The UI composes the read-only `ATLAS_STUDIO_MISSION_JOURNEY_V1` and `ATLAS_STUDIO_TASK_CONTEXT_V1` packets. Ownership remains split: integration owns packet composition, lifecycle owns execution and recovery semantics, and Improvement Plane owns recommendation calculations.

The native journey is: Mission Control → current mission and attention → knowledge with source provenance → candidate lane selection → task-context inspection. The UI states freshness, missing data, uncertainty, and authorization explicitly. It provides supported monitoring, continuity, and session handoff references; it does not fabricate execute, retry, resume, or permission controls.

Validation completed in the isolated candidate worktree:

- `npm run check`: frontend tests and production build pass (final rerun recorded with delivery).
- Playwright Chromium: focused mission-journey 2/2 and full suite 18 passed, 1 skipped (real bridge test is opt-in).
- Native Tauri Debian bundle built successfully. Executable SHA-256: `47ccbbdcae0046df8afc2b0106929e0d398a3de016680392202f9a090aa56d68`; Debian SHA-256: `74de69465489e4c6e47fe30995d6639c72643c28f136b68765faec7baf0ef3aa`.
- Live bridge `/v1/mission-journey` returned schema-valid LIVE data for `B0LK13/project-atlas`; `/v1/task-context` returns a bounded, schema-valid packet immediately; unavailable frontier and stack enrichment is listed as `NO_FRONTIER_MATRIX`/`NO_STACKS`.

External blockers are preserved honestly: task-context live composition currently exceeds the bridge deadline, and the integration contracts do not provide a mission catalog or native mutation authority. Documentation synchronization was attempted through the governed process but the remote returned HTTP 400 for insufficient Anthropic API credits; no receipt is claimed. This is a candidate handoff, not a merge, independent verification, release, or autonomous workstation claim.
