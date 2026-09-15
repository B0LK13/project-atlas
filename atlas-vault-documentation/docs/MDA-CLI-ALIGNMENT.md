# mda-cli Alignment

## Source baseline

- Repository: `B0LK13/mda-cli`
- Default branch: `main`
- Baseline commit: `b86c7f305fb8d2c84c3955fcc5f9e246b8a661bb`
- mda-cli package version at the inspected baseline: `0.2.9`

## Adopted conventions

1. Skill folders use a root `SKILL.md`.
2. A root `MDA-STANDARD.md` is loaded as companion governing context.
3. Skills may be selected with `--skill`, `--skill-dir`, `MDA_SKILL`, or `MDA_SKILL_DIR`.
4. External discovery includes Claude and Cursor skill directories.
5. Skill-local Python helpers live under `scripts/`.
6. Generated output uses an outer four-backtick Markdown fence that mda-cli can strip.
7. Raw Atlas evidence is never processed in-place.
8. Dry-run, atomic output, and machine-readable telemetry should be retained where available.

## Deliberate extension

mda-cli performs document transformation. This subproject adds immediate deterministic capture, immutable evidence, Atlas routing, spool fallback, receipts, and completion gating.

The capture and validation layer remains independent of model-provider availability.
