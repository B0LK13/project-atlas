# AS-CTRL-SPOOL-F1 — Spool sync binds destination vault identity

- Package: `AS-CTRL-SPOOL-F1`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION: `NOT_GRANTED`

## Finding

`spool_sync.synchronize` copied offline events into whatever
`--vault-root` was supplied and issued a passed receipt. Preflight
already rejects a mismatched vault pair; sync did not.

Independently reproduced on live main
`b87b4a226f4aa8b2f669edf112aa3476454f754f`: rehearsal session → dest
`vault-OTHER` / `other-uuid` returned rc=0 and wrote a receipt whose
session still claimed `atlas-rehearsal`.

## Remediation

Compare session `vault.vault_id` / `vault_uuid` to dest `.atlas/vault.json`
before copy. Honest same-identity offline sync still succeeds.

## Out of scope

- merge authorization
- promoting readiness grants

## Validation

See the PR body for commands actually run on the candidate object.
