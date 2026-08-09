# AS-SEC-CONT-001 — Continuous security fixture gates

| Field | Value |
|---|---|
| Package | `AS-SEC-CONT-001` |
| Directive | `D-PROJECT-ATLAS-1.0-MAX-PARALLEL-PLUS-2.0-PREP-001` |
| Surface | Docs + fixture unit gate only (no Core behavior change) |
| **ESTATE PILOT PASSED** | **NO** (not claimed) |
| **ATLAS_1_0_RELEASE_CERTIFIED / RELEASE** | **NO** (not claimed) |

## Purpose

Document the continuous security gates already present in Core and pin a
fixture-safe unit gate that re-asserts the secrets metadata-only invariant.
This package does **not** invent PILOT estate roots and does **not** weaken
fail-closed path checks.

## Continuous gates already in Core

### 1. Secrets scan — `project_atlas.secrets.scan_text` (NFR-004)

- Conservative regex scan for private keys, bearer tokens, API keys,
  passwords, connection strings, and cloud access keys.
- Returns `SecretFinding` metadata only (`pattern`, `confidence`,
  `redacted_hint`); matched secret content is never returned.
- Ingestion uses findings to quarantine secret-bearing sources and writes
  `generated/reports/secret-findings.json` without payload leakage.

### 2. Path refuse — fail-closed write bounds (AT-013)

- `scaffold.validate_output_path` refuses filesystem root, home directory,
  existing files, and non-empty non-vault directories before any write.
- Scaffold / index / xproj writers re-check each target with
  `Path.is_relative_to(resolved_root)` before touching disk.
- Ingestion path helpers reject absolute paths, backslashes, and `..`
  traversal so vault writes cannot escape the vault root.

### 3. Quarantine — secrets and adversarial instructions (AS-SEC-001)

- Secret hits during ingest → disposition `quarantined` (no canonical
  projection of the secret-bearing payload).
- `project_atlas.quarantine.scan_text` independently detects
  instruction-override / agent-mimicry patterns (metadata-only) and feeds
  the same quarantine boundary.
- Agent-event packages with vault-identity, skill, hash, or pipeline
  failures are quarantined before canonical projection.

## Related unit / integration tests

```bash
# Continuous secrets metadata-only gate (this package)
python -m pytest tests/unit/test_as_sec_cont_001_fixture_gates.py -q

# Adjacent Core security coverage (fixture-safe; no PILOT roots)
python -m pytest \
  tests/unit/test_semantic_models.py::test_secret_scanner_returns_redacted_metadata_only \
  tests/unit/test_scaffold.py \
  tests/unit/test_quarantine.py \
  tests/integration/test_as_sec_001_quarantine_boundary.py \
  -q
```

## Explicit non-claims

- **ESTATE PILOT PASSED** is **not claimed**.
- **RELEASE** / `ATLAS_1_0_RELEASE_CERTIFIED` is **not claimed**.
- No estate PILOT roots are invented by this package.
- Fail-closed path refuse behavior is documented, not relaxed.
