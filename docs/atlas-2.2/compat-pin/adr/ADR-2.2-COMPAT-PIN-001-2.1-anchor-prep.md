# ADR-2.2-COMPAT-PIN-001 — 2.1 compatibility anchor prep boundary

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-COMPAT-PIN-PREP-001 |
| Production slot | AS-2.2-COMPAT-PIN-001 (post-unlock) |
| Date | 2026-08-10 |

## Context

Atlas 2.2 intelligence packages (KCI, context compiler, hybrid retrieval,
temporal UX, KF fabric, etc.) depend on a **compatibility anchor** to the
certified 2.1 release line — mirroring how `AS-2.0-COMPAT-001` binds 2.0
packages to `atlas-1.0.0-compat`.

The 2.1 release path (`AS-REL-2.1` → `v2.1.0`) is **not complete** on the
current tip:

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO
```

Multiple landed 2.2 PREP packages already cite `AS-2.2-COMPAT-PIN-001` as a
post-unlock dependency. This ADR reserves the **docs-only expectation surface**
without publishing a 2.1 anchor or mutating `compat_anchor.py`.

## Decision

1. Add `docs/atlas-2.2/compat-pin/**` as the PREP home for compatibility pin
   expectations, contract stubs, and fixture sketches.
2. Declare `atlas-2.1.0-compat` as the **future** snapshot id; do **not** create
   `docs/releases/2.1.0/compatibility-anchor.json` on this tip.
3. Keep `atlas-1.0.0-compat` as the **live** consumer anchor until 2.1 cert.
4. Land presence tests only; do **not** mutate `src/project_atlas/compat_anchor.py`.
5. Do **not** edit `docs/atlas-2.2/README.md` (index owned by sibling worker).

## Consequences

- 2.2 PREP packages can cite a stable expectation inventory for compat posture.
- Research fixtures (`h-compat-pinned` supported / `h-release-certified` refuted)
  align with this boundary.
- Post-unlock `AS-2.2-COMPAT-PIN-001` has a reserved contract surface to implement
  against without redesign.

## Explicit non-claims

- `ATLAS_2_1_RELEASE_CERTIFIED = NO` (unchanged)
- Not `v2.1.0` released / tagged
- Not authentic estate PILOT evidence
- Fixture PASS ≠ release certification

## References

- `docs/atlas-2.0/COMPATIBILITY.md`
- `docs/releases/1.0.0/compatibility-anchor.json`
- `src/project_atlas/compat_anchor.py` (read-only reference; do **not** mutate)
- `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`
- `docs/atlas-2.2/compat-pin/AS-2.2-COMPAT-PIN-PREP-001.md`
