# Charter + maturity matrix — architecture (PREP)

Package: **AS-2.2-DOC-CHARTER-PREP-001**

Status: **PREP ONLY**. This document reserves the fail-closed architecture for
how Atlas 2.2 documents its prep charter and maturity posture — without
stamping release certification or mutating runtime intelligence modules on the
current tip.

## Certification posture

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO
```

## Layer model

```text
Layer A — Certified release charters (read-only references)
  docs/atlas-2.0/          2.0 RELEASE CERTIFIED (fixture waiver)
  docs/atlas-2.1/CHARTER.md + FEATURE-MATURITY-MATRIX.md   [2.1 line — not yet cert]

Layer B — 2.2 PREP charter + matrix draft (this package)
  docs/atlas-2.2/CHARTER.md              deepened prep charter
  doc-charter/FEATURE-MATURITY-MATRIX.md draft rows for landed PREP packages
  doc-charter/fixtures/maturity-matrix.fixture.json  machine-readable rehearsal

Layer C — Post-unlock production refresh (blocked)
  AS-2.2-DOC-CHARTER-001 → authoritative 2.2 charter + certified matrix
```

## Charter succession

| Phase | Authoritative charter | Matrix posture |
|---|---|---|
| Pre-2.1 cert (now) | 2.1 charter vocabulary; 2.2 prep charter (this PREP) | Draft rows only; `DOCUMENTATION_ONLY` / `FIXTURE_ONLY` |
| Post-2.1 cert + unlock | `AS-2.2-DOC-CHARTER-001` refresh | Matrix rows may promote to `CONTRACT_ONLY` / `BOUNDED` as packages land |
| Post-2.2 cert | `AS-REL-2.2-001` | Matrix frozen for `v2.2.0` audit |

## Matrix row shape

Each row inventories one package with:

| Column | Meaning |
|---|---|
| Package id | Stable AS-2.2-* identifier |
| Maturity | Normative class from charter vocabulary |
| Evidence | Docs path / fixture tree (not runtime on PREP tip) |
| 2.2 disposition | `PREP` / `BLOCKED` / `FEEDS` (production slot) |

Machine-readable rows validate against `charter-maturity-row.schema.json`.

## First READY slot (strategy DAG)

Per `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`, `AS-2.2-DOC-CHARTER-001`
is the **first** package READY after unlock — before compat pin and intelligence
production paths. This PREP reserves that slot without claiming unlock.

## Explicit non-claims

- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not authentic estate PILOT evidence
- Not a mutation of `docs/atlas-2.2/README.md`
- Not promotion of stub schemas to `src/project_atlas/schemas/`
