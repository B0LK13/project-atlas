# Atlas 2.2 - Feature maturity matrix (PREP draft)

Tip baseline: `70889b1` (post #249 INDEX-016; includes SEMIDX #248, CROSSWALK-SYNC #246, ADV-POOL #243, FIXTURE-ROLLUP #242).
Tree (`docs/atlas-2.2` at tip): `92370052bfc577123821db5f4126ab8cda224794`.
Classes per [`../CHARTER.md`](../CHARTER.md).

**Status: PREP ONLY** - draft rows for audit rehearsal; not release certification.

| Capability / package | Maturity | Evidence (docs) | 2.2 disposition |
|---|---|---|---|
| AS-2.2-RET-HYBRID-001 | DOCUMENTATION_ONLY | `HYBRID-RETRIEVAL-2.md`, `benchmarks/`, `fixtures/hybrid-retrieval/` | PREP - feeds RET-CTX |
| AS-2.2-CTX-COMPILER-001 | FIXTURE_ONLY | `ctx-compiler/`, `contracts/ctx-compiler/`, `fixtures/ctx-compiler/` | PREP - feeds RET-CTX |
| AS-2.2-MEM-GOV-001 | FIXTURE_ONLY | `mem-gov/`, `contracts/mem-gov/`, `fixtures/mem-gov/` | PREP |
| AS-2.2-KCI-ENGINE-PREP-001 | DOCUMENTATION_ONLY | `kci-engine/`, `AS-2.2-KCI-ENGINE-PREP-001.md` | PREP - feeds KCI-001 |
| AS-2.2-DOD-COMPILER-001 | FIXTURE_ONLY | `dod-compiler/`, `contracts/dod-compiler/`, `fixtures/dod-compiler/` | PREP |
| AS-2.2-TIME-MACHINE-001 | FIXTURE_ONLY | `time-machine/`, `AS-2.2-TIME-MACHINE-001.md` | PREP - feeds TEMPORAL |
| AS-2.2-REALITY-LIVE-001 | FIXTURE_ONLY | `reality-live/`, `contracts/reality-live/` | PREP |
| AS-2.2-REALITY-GAP-PREP-001 | FIXTURE_ONLY | `reality-gap/` | PREP |
| AS-2.2-RESEARCH-001 | FIXTURE_ONLY | `research/`, `contracts/research/`, `fixtures/research/` | PREP - feeds ASK2 |
| AS-2.2-CONFLICT-UX-PREP-001 | FIXTURE_ONLY | `conflict-ux/`, `conflict-ux/contracts/`, `conflict-ux/fixtures/` | PREP - feeds CONFLICT-UX-001 |
| AS-2.2-XPROJ-CONTRACT-PREP-001 | FIXTURE_ONLY | `xproj/`, `xproj/contracts/`, `xproj/fixtures/` | PREP - feeds XPROJ / ESTATE-OPS |
| AS-2.2-KF2-FABRIC-PREP-001 | FIXTURE_ONLY | `kf2-fabric/`, `kf2-fabric/contracts/`, `kf2-fabric/fixtures/` | PREP - feeds KF2-FABRIC-001 |
| AS-2.2-ASK2-DEEPEN-PREP-001 | FIXTURE_ONLY | `ask-atlas-2/`, `ask-atlas-2/contracts/`, `ask-atlas-2/fixtures/` | PREP - feeds ASK2 |
| AS-2.2-INTEL-SLICE-PREP-001 | FIXTURE_ONLY | `intel-slice/`, `intel-slice/fixtures/` | PREP - feeds INTEL-SLICE-001 |
| AS-2.2-CHATGPT-LIVE-PREP-001 | FIXTURE_ONLY | `chatgpt-live/`, `chatgpt-live/contracts/`, `chatgpt-live/fixtures/` | PREP - optional post-unlock |
| AS-2.2-TEMPORAL-UX-PREP-001 | FIXTURE_ONLY | `temporal-ux/`, `temporal-ux/contracts/`, `temporal-ux/fixtures/` | PREP - feeds TEMPORAL-001 |
| AS-2.2-COMPAT-PIN-PREP-001 | FIXTURE_ONLY | `compat-pin/`, `compat-pin/contracts/`, `compat-pin/fixtures/` | PREP - feeds COMPAT-PIN-001 |
| AS-2.2-ESTATE-OPS-PREP-001 | FIXTURE_ONLY | `estate-ops/`, `estate-ops/contracts/`, `estate-ops/fixtures/` | PREP - feeds ESTATE-OPS-001 |
| AS-2.2-PREP-FIXTURE-ROLLUP-001 (#242) | DOCUMENTATION_ONLY | `AS-2.2-PREP-FIXTURE-ROLLUP-001.md`, `FIXTURE-PLAN.md`, `PACKAGE-CONTRACT-STUBS.md` | PREP - deepen fixture index (docs rollup) |
| AS-2.2-ADV-POOL-001 (#243) | DOCUMENTATION_ONLY | `adv-pool/`, `adv-pool/ADV-MATRIX.md` | PREP - ADV threat sketch (not live ADV suite) |
| AS-2.2-ROADMAP-CROSSWALK-SYNC-001 (#246) | DOCUMENTATION_ONLY | `roadmap-crosswalk/`, `CROSSWALK.md` | PREP - crosswalk tip sync after rollup/ADV-POOL |
| AS-2.2-RET-SEMIDX-PREP-001 (#248) | FIXTURE_ONLY | `ret-semidx/`, `ret-semidx/contracts/`, `ret-semidx/fixtures/` | PREP - semantic slot **default-off**; reserved SEMIDX-001 |
| AS-2.2-DOC-CHARTER-001 | BLOCKED | strategy DAG first READY slot | BLOCKED until unlock |

## Matrix highlights

1. **All PREP rows** are `DOCUMENTATION_ONLY` or `FIXTURE_ONLY` - no live intelligence runtime on tip.
2. **Production slots** (`*-001` without PREP suffix) remain `BLOCKED` until unlock.
3. **Authentic estate PILOT** is not satisfied by any row in this matrix.
4. **`ATLAS_2_1_RELEASE_CERTIFIED = NO`** and **`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO`** on this tip.
5. **SEMIDX** remains disabled by default; enabling without an index contract fails closed.
6. Machine-readable rehearsal: [`fixtures/maturity-matrix.fixture.json`](fixtures/maturity-matrix.fixture.json).

## Explicit non-claims

- Not `v2.1.0` / `v2.2.0` release certification
- Not authentic estate PILOT evidence
- Not promotion of stub schemas to package data
- Demo VERIFIED ≠ release unlock / ≠ authentic PILOT PASS
