# AS-ADV-RELEASE-002 — Clean-clone RC hardening (RELEASE = NO)

| Field | Value |
|---|---|
| Mission | AS-ADV-RELEASE-002 |
| Parent package | AS-ADV-RELEASE-001 (`atlas adv certify`) |
| New matrix case | `clean_clone_replay` |
| Report | `generated/ops/adv-release-cert-report.json` |

## Purpose

Deepen release-candidate (RC) hardening for **clean-clone replay** without
claiming RELEASE CERTIFIED. Operators preparing a disposable certification
run should be able to prove that two fresh vaults, fed the **same** discover
manifest, land on byte-identical stable planes.

## Procedure (matrix case `clean_clone_replay`)

1. Seed a disposable source tree (fixture project marker + README).
2. Run `discover` once; persist a single shared `manifest.json`.
3. `atlas init` (scaffold) two empty disposable vaults (`vault-a`, `vault-b`).
4. On each vault, sequentially: `ingest` → `build-indexes` → `validate`
   using the **identical** manifest bytes.
5. Compare stable planes only:
   - `projects/`
   - `state/`
   - `generated/indexes/`
   - `00-system/`
6. Pass when the stable-plane key set is non-empty and every key is
   byte-identical across the two vaults (E2E-style compare).

Run via the existing CLI (no new subcommand):

```bash
atlas adv certify --work-root <disposable-work> [--report-vault <vault>]
```

## Relation to `determinism_pipeline`

| Case | What it proves |
|---|---|
| `determinism_pipeline` | Same vault, second pass is idempotent |
| `clean_clone_replay` | Two independent vaults from one manifest match |

Both are operational fixture gates. Neither stamps a release.

## Explicit non-claims

- RELEASE CERTIFIED = **NO** (`release_certified: false` always)
- ESTATE PILOT PASSED = **NO**
- WEB APPLICATION ACCEPTED = **NO**
- Clean-clone pass ≠ production cutover authority
