# Versioning

## Current state

Project Atlas is **pre-1.0**. The installable Python package version is
declared in `pyproject.toml` (currently `0.1.0`). There is no maintained
multi-branch release train and no claim of automated version bumping.

## What is versioned

| Surface | Source of truth | Notes |
| --- | --- | --- |
| Python package `project-atlas` | `[project].version` in `pyproject.toml` | SemVer intent; pre-1.0 means breaking changes may occur without a major bump only when explicitly Owner-authorized and documented |
| Shared contracts (`atlas_contracts`) | Same package / schema files under `src/atlas_contracts/` | Schema changes are evidence-bound work packages, not silent edits |
| OKF / domain schemas | JSON Schema files shipped as package data | Compatibility expectations are documented per work package |
| Work packages / ADRs / receipts | Git commit SHA (and tree when recorded) | Package completion is not a software release |
| Control plane (`atlas-vault-documentation/`) | Sibling deliverable; own manifests/tests | Versioned/released only under explicit Owner authorization |

## SemVer intent (when a release is authorized)

When the Owner authorizes a software release:

- Use Semantic Versioning: `MAJOR.MINOR.PATCH`.
- Git tags, if created, use the form `vMAJOR.MINOR.PATCH` and must point at
  the exact authorized release commit.
- A work-package completion, local integration, or GitHub PR merge is **not**
  automatically a release.
- CI does **not** create tags or GitHub Releases automatically.

## Honesty constraints

- Do not invent a release bot, changelog automation, or registry publish
  pipeline that does not exist.
- Do not claim signed tags or verified releases until those controls are
  implemented and independently verified.
- Pre-1.0 consumers should pin to an exact commit SHA when reproducibility
  matters more than a floating version number.

See `RELEASING.md` for the authorization and publication sequence.
