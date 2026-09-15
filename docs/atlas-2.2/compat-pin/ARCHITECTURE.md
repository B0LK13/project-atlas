# Compatibility pin — architecture (PREP)

Package: **AS-2.2-COMPAT-PIN-PREP-001**

Status: **PREP ONLY**. This document reserves the fail-closed architecture for
how Atlas 2.2 intelligence packages declare compatibility with the future
`v2.1.0` release anchor — without publishing that anchor or mutating runtime
consumers on the current tip.

## Certification posture

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO
```

## Layer model

```text
Layer A — Certified anchors (read-only references)
  atlas-1.0.0-compat     docs/releases/1.0.0/compatibility-anchor.json  [CERTIFIED]
  atlas-2.1.0-compat     docs/releases/2.1.0/compatibility-anchor.json  [FUTURE — not on tip]

Layer B — PREP expectation inventory (this package)
  compat-expectation.fixture.json
  consumer scenario rows (KCI / CTX / RET / DoD / …)

Layer C — Post-unlock production consumer (blocked)
  AS-2.2-COMPAT-PIN-001 → compat verify extension / 2.1 anchor loader
```

## Anchor succession

| Phase | Active anchor | 2.x consumer rule |
|---|---|---|
| Pre-2.1 cert (now) | `atlas-1.0.0-compat` | 2.0/2.1 packages bind 1.0; 2.2 PREP cites future 2.1 pin only |
| Post-2.1 cert + unlock | `atlas-2.1.0-compat` | 2.2 intelligence packages must pin 2.1; 1.0 remains historical |

## Drift classes (carried from 2.0)

| Class | Description | 2.2 PREP response |
|---|---|---|
| **Hard** | Authority / identity / provenance contract change | Fail closed; require new major snapshot |
| **Soft** | Additive schema fields with defaults | Allowed with compat test green |
| **Web** | UI invariant regression | Block UX packages; ADR-008 gate |
| **Graph** | Derived projection format change | Consume-only adapter version bump |

## Consumer packages (post-unlock dependents)

Per `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`, these packages declare a
compat-pin dependency after unlock:

| Package | Compat posture |
|---|---|
| `AS-2.2-KF2-FABRIC-001` | Requires 2.1 anchor before estate fabric production |
| `AS-2.2-RET-CTX-001` | Requires 2.1 anchor before hybrid retrieval production |
| `AS-2.2-TEMPORAL-001` | Requires 2.1 anchor before bitemporal UX production |
| `AS-2.2-KCI-001` | Engine refuses run without 2.1 compat pin |
| `AS-2.2-CTX-COMPILER-001` | Context compiler depends on compat pin post-unlock |

PREP fixtures record these as **declared expectations only** — not enforced
runtime gates on this tip.

## Truth boundaries

- PREP inventory ≠ published `docs/releases/2.1.0/` tree
- Expectation fixture ≠ `atlas compat verify` success for 2.1
- 1.0 anchor load success ≠ 2.1 release certification
- Research hypothesis `h-compat-pinned` (supported) ≠ `h-release-certified` (refuted)

## Explicit non-claims

- Not `v2.1.0` released
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not mutation of `project_atlas.compat_anchor`
- Not authentic estate PILOT evidence
