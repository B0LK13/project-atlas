# AS-ADV-RELEASE-004 - Migration/recovery RC deepen (RELEASE = NO)

Mission: deepen fixture release-candidate recovery evidence without granting
release authority. The operational report keeps `release_certified: false`.

## Matrix case: `migration_recovery_replay`

1. Build a disposable fixture vault through discover, ingest, index, and validate.
2. Capture the byte-level stable plane and its framed digest summary.
3. Create one deterministic stage-only promote orphan beside a canonical project
   note, matching the existing AS-CORE2-009 interrupted-promotion pattern.
4. Run `recover_promote_orphans`; require one recovered transaction, removal of
   the staged orphan, and preservation of the canonical bytes.
5. Validate, replay ingest/index/validate from the same manifest, then require
   byte-identical stable planes and a second recovery no-op.

This case is deterministic: it uses a fixed transaction identifier, objective
counts, byte comparisons, and digests. No timing threshold participates.

Run through the existing command:

```bash
atlas adv certify --work-root <disposable-work> [--report-vault <vault>]
```

## Explicit non-claims

- RELEASE = **NO**
- RELEASE CERTIFIED = **NO** (`release_certified: false` always)
- ESTATE PILOT PASSED = **NO**
- WEB APPLICATION ACCEPTED = **NO**
- Recovery replay pass is fixture RC evidence, not production migration authority.
