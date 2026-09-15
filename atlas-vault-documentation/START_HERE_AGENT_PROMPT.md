# Coding Agent Kickoff — Atlas Vault Documentation Skill

Implement this subproject as the universal documentation transaction layer for Project Atlas.

## Read first

1. `README.md`
2. `PRP.md`
3. `SKILL.md`
4. `MDA-STANDARD.md`
5. `references/ATLAS-DOCUMENTATION-CONTRACT.md`
6. `references/MDA-CLI-INTEGRATION.md`
7. `ACCEPTANCE_TESTS.md`
8. `IMPLEMENTATION_ROADMAP.md`

## Immediate assignment

Execute **AS-WP-001 — Deterministic Capture and Validation Hardening**.

### Required work

1. Review `scripts/capture_event.py` and `scripts/check_documentation.py`.
2. Add automated tests covering AS-002 through AS-008 and AS-018.
3. Add configuration-file discovery and environment fallback.
4. Ensure capture is atomic and path-safe.
5. Ensure duplicate event IDs fail closed.
6. Expand secret-redaction tests without logging secret values.
7. Add JSON output contracts.
8. Run the complete validation suite.
9. Document this implementation through the skill itself.

### Constraints

- No network or LLM required.
- Do not mutate raw evidence.
- Do not weaken strict spool behavior.
- Do not write outside configured roots.
- Use mda-cli conventions.
- Record exact evidence.

### Completion report

Return files changed, behavior, exact commands and results, Atlas event IDs, limitations, next work package, and `ATLAS-DOC-RECEIPT`.
