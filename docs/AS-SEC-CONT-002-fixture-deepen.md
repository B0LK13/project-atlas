# AS-SEC-CONT-002 — Continuous security fixture deepen

| Field | Value |
|---|---|
| Package | `AS-SEC-CONT-002` |
| Parent | `AS-SEC-CONT-001` |
| Directive | `D-PROJECT-ATLAS-1.0-MAX-PARALLEL-PLUS-2.0-PREP-001` |
| Surface | Docs + fixture unit gates (no Core behavior change) |
| **ESTATE PILOT PASSED** | **NO** |
| **RELEASE CERTIFIED** | **NO** |
| **WEB APPLICATION ACCEPTED** | **NO** |

## Purpose

Deepen continuous security fixture coverage beyond SEC-CONT-001:

1. Path-refuse fail-closed (`scaffold.validate_output_path`) for home / FS-root style targets
2. Additional secrets patterns (private key + cloud access key) still metadata-only
3. Explicit non-claims for PILOT / RELEASE / WEB ACCEPTED

This package does **not** invent PILOT estate roots and does **not** weaken
fail-closed path checks.

## Gates

### Path refuse (AT-013)

`validate_output_path` must refuse unsafe destination classes before any vault
scaffold write. Fixture tests assert refusal for home-directory and filesystem
root style targets without mutating production estate.

### Secrets metadata-only (NFR-004)

`scan_text` findings for private-key and cloud-access-key patterns must never
echo matched secret content into `pattern` / `confidence` / `redacted_hint`.

## Explicit non-claims

- ESTATE PILOT PASSED = **NO**
- RELEASE CERTIFIED = **NO**
- WEB APPLICATION ACCEPTED = **NO**
- Production SYNC certified = **NO**
