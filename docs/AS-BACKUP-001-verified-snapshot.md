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
