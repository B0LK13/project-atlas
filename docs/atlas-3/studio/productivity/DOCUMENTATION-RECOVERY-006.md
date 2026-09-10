# Documentation recovery 006

Status: `DOCUMENTATION_RECOVERY_BLOCKED`
Date: 2026-09-10

The earlier check against the main checkout's `.atlas-vault` was not the vault
used by the Studio recovery sessions. The preserved recovery checkout is:

`/home/gebruiker/Downloads/atlas-studio-recovery-kjbouvd1/recovered-checkout`

Its session records configure the offline spool root as
`recovered-checkout/.atlas-spool`; no canonical Vault identity was found in the
recovery bundle. The Studio worktree is `/tmp/atlas-native-daily-workspace-001`.

## Inventory

The recovered spool contains 27 raw `AE-*.md` events, zero normalized outputs,
zero routed or validated outputs, 27 remaining pending events, and one
normalization failure marker. Four active sessions have no receipt:

| Session | Task | Captured | Normalized | Routed | Verified | Receipt |
|---|---|---:|---:|---:|---:|---|
| `AS-20260909T142418Z-generic-project-atlas-b271a70f` | `unknown` | 4 | 0 | 0 | 0 | none |
| `AS-20260909T144124Z-generic-project-atlas-a099c334` | close acceptance gaps | 2 | 0 | 0 | 0 | none |
| `AS-20260909T152659Z-generic-project-atlas-c7995aed` | resume and deliver | 4 | 0 | 0 | 0 | none |
| `AS-20260909T161732Z-generic-project-atlas-f6efb2ce` | final delivery gates | 9 | 0 | 0 | 0 | none |

The supported structural check, pointed at the actual spool parent, reports 27
pending events and three malformed raw records (missing frontmatter or
`captured_at`). This is a structural result, not synchronization completion.

## Normalizer attempt

The real configured executable is
`/home/gebruiker/Downloads/atlas-studio-recovery-kjbouvd1/normalizer-venv/bin/mda`.
`mda --check` reports MDA 0.2.9, provider `anthropic`, model
`claude-sonnet-4-20250514`, and an Anthropic key present. Provider selection is
environment based; no credential value is recorded here.

One real pending event was run through `normalize_event.py` using the supported
`mda` basename with the normalizer virtualenv on `PATH`. The normalizer reached
Anthropic and returned HTTP 400: credit balance too low. No normalized file or
receipt was produced. Raw evidence remains unchanged. No unchanged retry was
performed.

## Hook diagnosis

The recovered `.cursor/hooks.json` used `python`, which is absent from `PATH`;
`/usr/bin/python3` is available. Both hook commands were changed to `python3`
and validated with exit code 0. Repair commit in the recovered checkout:
`3fb2d71c75035a65b4afcd8f052e0fd828787ea6`.

The remaining blocker is external Anthropic credit availability and the missing
canonical Vault target required for final routing/receipt issuance.

