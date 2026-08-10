# Compatibility pin — invariants (PREP)

Status: **PREP ONLY**. These rules freeze the fail-closed posture for
`AS-2.2-COMPAT-PIN-PREP-001` fixtures and future `AS-2.2-COMPAT-PIN-001` work.

## Certification posture

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO
```

Unlock remains `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` after
`v2.1.0`. Fixture rehearsal under this tree grants **no** WEB / RELEASE /
PILOT credit.

## Hard invariants

| ID | Rule | Shorthand |
|---|---|---|
| AS-COMPAT-PIN-INV-TRUTH-001 | PREP expectation ≠ published 2.1 anchor | **PREP ≠ ANCHOR** |
| AS-COMPAT-PIN-INV-RELEASE-001 | Prep fixtures set `atlas_2_1_release_certified = false` | **NO 2.1 RELEASE STAMP** |
| AS-COMPAT-PIN-INV-PIN-001 | Future snapshot id is `atlas-2.1.0-compat`; not yet published | **FUTURE PIN ONLY** |
| AS-COMPAT-PIN-INV-1.0-001 | Live consumer remains `atlas-1.0.0-compat` until 2.1 cert | **1.0 LIVE / 2.1 FUTURE** |
| AS-COMPAT-PIN-INV-WINS-001 | Post-cert: 2.1 wins dependency conflicts (mirrors 1.0 pattern) | **2.1 WINS (post-cert)** |
| AS-COMPAT-PIN-INV-PILOT-001 | No PILOT root invent on prep fixtures | **NO PILOT INVENT** |
| AS-COMPAT-PIN-INV-RUNTIME-001 | No mutation of `compat_anchor.py` on this tip | **NO RUNTIME MUTATION** |

## Negative outcomes (expected fail-closed)

| Attempt | Expected error key |
|---|---|
| Set `release_certified: true` for 2.1 on prep tip | `compat-pin-prep-release-certified-forbidden` |
| Invent PILOT roots to justify anchor | `compat-pin-prep-pilot-invent-forbidden` |
| Publish `docs/releases/2.1.0/` on prep tip | `compat-pin-prep-anchor-publish-forbidden` |

## Allowed documentation posture

- Reference `AS-2.0-COMPAT-001` and 1.0 anchor **conceptually**
- Cite roadmap package `AS-2.2-COMPAT-PIN-001` as the post-unlock production slot
- Keep all new files under `docs/atlas-2.2/compat-pin/**` (+ unique unit test)
- Do **not** edit `docs/atlas-2.2/README.md`
