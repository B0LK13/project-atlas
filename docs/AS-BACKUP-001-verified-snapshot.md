# AS-BACKUP-001 — Verified Atlas Snapshot

| Field | Value |
|---|---|
| Package | `AS-BACKUP-001` (alias `BACKUP-001`) |
| Umbrella | `AS-OPS-001` (first bounded slice) |
| Truth plane | **Operational durability** — snapshot ≠ authority / claim / temporal / graph truth |

## Commands

```bash
atlas snapshot --vault <vault> --output <bundle-dir> [--cp <cp>] [--include-d5]
atlas snapshot --verify --bundle <bundle-dir>
atlas restore  --bundle <bundle-dir> --output <empty-target> [--tier T2|T3] \
               [--expect-vault-logical-id <id>]
```

## Cold regenerability matrix

```text
MUST BACK UP = D1 + D2 + D3 + D4 + D6
OPTIONAL WARM = D5 (never truth alone)
NEVER         = EPHEMERAL (.*.atlas-stage / .*.atlas-backup / TMP)
CERTIFY       = cold path (no D5) → rebuild indexes → atlas validate green
```

## Completeness contract (RECOVERY_GATE=PASS)

The cold bundle captures **all** persisted, non-ephemeral vault content so a
restore reproduces the full vault byte-for-byte, except the declared
derived-regenerable warm plane D5 (`generated/`, rebuilt via
`atlas build-indexes` / `atlas build-portfolio`). `classify_vault_path` maps
every top-level area to a domain, including the OKF category directories
(`capabilities/`, `decisions/`, `infrastructure/`, `standards/`,
`technologies/`) and root `log.md` → **D2**, and knowledge-compile receipts
(`receipts/claims/*.json`) → **D3** (integrity proofs travelling with the state
plane; not control-plane D4). `create_snapshot` **fails closed** on any
persisted, non-ephemeral file it cannot classify — a bundle that would silently
omit content is refused rather than written (root cause of the earlier F1
omission). Empty structural scaffold directories carry no member bytes;
`restore --scaffold` re-lays the deterministic `atlas init` skeleton onto the
empty target before members are restored, giving full structural parity without
tripping the empty-target guard.

## Certification (fixture only)

```text
CREATE → SNAPSHOT → CORRUPT COPY → RESTORE → VALIDATE → COMPARE
```

Live authoritative destroy+restore is **forbidden** for this package (OPS-004).

## Fail-closed

Digest mismatch, identity / wrong-mount mismatch, unbalanced HUMAN markers,
non-empty restore targets, path root/home, and mid-promote orphans all abort
non-zero with no silent heal.

## Library

`project_atlas.backup`: `create_snapshot`, `verify_bundle`, `restore_bundle`,
`compare_member_digests`, `collect_identity_samples`.
