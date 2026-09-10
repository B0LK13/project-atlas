# Native Operator Experience 006

## Candidate

- Repository: `https://github.com/B0LK13/project-atlas.git`
- Branch: `feat/atlas-native-daily-workspace-001`
- HEAD: `92568e14a206a3c918493f97b5253ca374fb5148`
- Tree: `68c4c0154601051eec8a5fca942798135a2be615`
- Prior accepted candidate preserved: `664325fc` (`atlas-studio-page-purpose-003`)

## Implemented

Mission Control now has a local, explicitly scoped filter over loaded attention records. It reports loaded and matching counts, handles no matches, and provides a keyboard reachable clear action. Selection remains inspectable when a filter excludes it. Persisted attention and lane selections now require version 1 and `PROJECTION` source mode, and entering fixture mode clears them, so malformed, obsolete, or cross-mode state is discarded without affecting source truth.

## Validation

- `npm run check`: passed (typecheck, 46 unit tests, production build).
- Browser: new loaded-record filter journey passed with Playwright using the documented `chromiumSandbox:false` environment workaround; existing Mission Control and Mission Journey suites remain passing from the preserved candidate.
- Native: release executable launched under `DISPLAY=:0` for an 8-second smoke window (expected timeout while the app remained running).
- Fresh native artifacts:
  - executable SHA-256 `0438b41843ea211e10b920c1a03908be6c532b1de9354cf8fcf6ae03cdb8d82e`
  - AppImage SHA-256 `7e64ddba6adaacf68a67bb02f19cb18651160b87e49cabb3d9b49baa6d85fa12`
  - Debian SHA-256 `6e31e3940c7a234661453f8f4cc1178c6b0e55554d69be1477f6464431bd8718`

## Scope and limitations

Native accessibility and visual checks for the complete operating-condition matrix remain covered by the prior candidate evidence; the new filter behavior has browser coverage and a fresh native build/smoke only. Candidate evidence, mission catalog, dependency graph, knowledge, history, and canonical documentation routing remain external contract blockers already recorded in `DOCUMENTATION-RECOVERY-006.md`; no backend or authority behavior was changed. Documentation recovery remains blocked: 27 raw events preserved, 0 normalized/routed/validated, 27 pending, no receipt, with the prior provider-credit failure unchanged.
