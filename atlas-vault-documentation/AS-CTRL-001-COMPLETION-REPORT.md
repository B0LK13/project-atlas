# AS-CTRL-001 — Universal Agent Bootstrap and Atlas Documentation Enforcement

## Disposition

AS-CTRL-001 IMPLEMENTATION COMPLETE — CERTIFICATION PENDING.

The control layer is implemented, but certification remains pending until a
managed launcher run is demonstrated with a real normalize → verify → route
pipeline and the required spool synchronization probe.

## Implemented

- Canonical `skill/SKILL.md`, manifest and generated SHA-256.
- Deterministic generated adapters under `.generated-agent-instructions/`.
- Logical Vault identity via `.atlas/vault.json`.
- Repository project bootstrap via `.atlas/project.yaml`.
- Preflight Vault, skill, version, adapter and spool checks.
- Globally unique agent/session identities.
- Managed launcher and unified `atlas-agent document` command surface.
- Automatic session-start capture.
- Machine-readable session state and receipt gate.
- Strict rejection of missing milestone events, pending strict spool, or incomplete normalize/verify/route counts.
- Wrong-Vault, adapter-drift, offline-spool, concurrency and receipt-gate tests.
- Agent capability registry, protected-path declaration, schemas and contracts.

## Validation evidence

- Control-focused tests: 7 passed after the final fixture correction.
- Mypy: 106 source files, no issues.
- Ruff: passed.
- Parent repository suite: 54 passed.
- Full subproject suite: 141 passed.
- Adapter verification CLI: passed.

## Certification blockers

1. Run `atlas-agent run` against a disposable Vault with a configured mock or local MDA executable and prove a complete normalized, verified and routed session receipt.
2. Synchronize an offline spool and prove duplicate-free replay.
3. Add or run the final direct-protected-path and supervised-subagent probes.

## Security and compatibility

Wrong logical Vault IDs are rejected even when the path is writable. Skill hash
and adapter drift fail closed. Spool mode is explicit and strict completion
remains blocked while events are pending. Existing AS-WP-001 through AS-WP-005
capture, normalization, routing, Graphify and validation contracts are not
replaced.
