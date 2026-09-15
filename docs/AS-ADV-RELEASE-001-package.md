# AS-ADV-RELEASE-001 — Fixture advanced release certification

| Field | Value |
|---|---|
| Package | AS-ADV-RELEASE-001 |
| CLI | `atlas adv certify --work-root <dir> [--report-vault <vault>]` |
| Report | `generated/ops/adv-release-cert-report.json` |

## Matrix

- `recovery_promote_noop` — CORE2-009 clean vault
- `recovery_snapshot_roundtrip` — BACKUP-001 create/verify/restore
- `determinism_pipeline` — twin pipeline digest equality (same vault)
- `clean_clone_replay` — two disposable vaults + identical manifest → stable plane compare (AS-ADV-RELEASE-002)
- `perf_baseline_fixture` — fixture-scale timings (ms)

See `docs/AS-ADV-RELEASE-002-clean-clone.md` for clean-clone RC hardening notes.

## Explicit non-claims

- RELEASE CERTIFIED = **NO** (`release_certified: false` always)
- ESTATE PILOT PASSED = **NO**
- WEB APPLICATION ACCEPTED = **NO**
