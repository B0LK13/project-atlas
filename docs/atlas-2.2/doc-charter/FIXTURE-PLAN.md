# Charter + maturity matrix — fixture plan (PREP)

Package: **AS-2.2-DOC-CHARTER-PREP-001**

## Fixture families

| Family | File(s) | Purpose |
|---|---|---|
| **Matrix inventory** | `maturity-matrix.fixture.json` | Machine-readable draft rows for landed PREP packages |
| **Negative — release cert** | `negative-release-certified.expect.json` | Fail-closed when prep claims 2.1 release certified |
| **Negative — PILOT invent** | `negative-pilot-invent.expect.json` | Fail-closed when prep invents authentic PILOT roots |

## Matrix inventory rows (minimum)

The inventory fixture must include at least these PREP packages (aligned with
`docs/atlas-2.2/README.md` index through tip #197):

- `AS-2.2-RET-HYBRID-001`
- `AS-2.2-CTX-COMPILER-001`
- `AS-2.2-MEM-GOV-001`
- `AS-2.2-KCI-ENGINE-PREP-001`
- `AS-2.2-DOD-COMPILER-001`
- `AS-2.2-TIME-MACHINE-001`
- `AS-2.2-REALITY-LIVE-001`
- `AS-2.2-REALITY-GAP-PREP-001`
- `AS-2.2-RESEARCH-001`
- `AS-2.2-CONFLICT-UX-PREP-001`
- `AS-2.2-XPROJ-CONTRACT-PREP-001`
- `AS-2.2-KF2-FABRIC-PREP-001`
- `AS-2.2-ASK2-DEEPEN-PREP-001`
- `AS-2.2-INTEL-SLICE-PREP-001`
- `AS-2.2-CHATGPT-LIVE-PREP-001`
- `AS-2.2-TEMPORAL-UX-PREP-001`
- `AS-2.2-COMPAT-PIN-PREP-001`
- `AS-2.2-ESTATE-OPS-PREP-001`

Plus one row for the production slot `AS-2.2-DOC-CHARTER-001` (`BLOCKED` disposition).

## Invariant block (all positive fixtures)

```json
{
  "pilot_roots": 0,
  "authentic_estate_pilot_passed": false,
  "atlas_2_1_release_certified": false,
  "atlas_2_2_intelligence_unlocked": false,
  "evidence_class": "fixture-only"
}
```

## Explicit non-claims

- Fixture PASS ≠ authentic PILOT PASS
- Matrix draft ≠ `v2.2.0` certification
- No runtime modules under `src/` required for fixture rehearsal
