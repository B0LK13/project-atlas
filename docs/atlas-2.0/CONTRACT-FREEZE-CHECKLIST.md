# Atlas 2.0 — Contract freeze checklist (prep)

Status: **PREP ONLY** — `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

Checklist for freezing §98 package contracts before any production 2.0
implementation. Every item remains **unchecked / NO** until a governor
records evidence after `ATLAS_1_0_RELEASE_CERTIFIED`.

This file is inventory and process only. Checking a box here does **not**
authorize `src/` work or dependency-bearing schemas.

## Preconditions (all NO)

| # | Precondition | Status |
|---|---|---|
| P1 | `ATLAS_1_0_RELEASE_CERTIFIED = YES` | [ ] **NO** |
| P2 | Compatibility snapshot published (HEAD/TREE/tag) | [ ] **NO** |
| P3 | Owner authorization to freeze 2.0 contract names | [ ] **NO** |
| P4 | `ATLAS_2_0_IMPLEMENTATION_READY` may be considered (still separate flip) | [ ] **NO** |

## Observed prep baseline pin (not release certification)

- Tip commit: `b57cceb383dca8d4a8c967da58abfc799386a829`
- Tip tree: `7efe25dccee4c91a9095cbf4743865274c4e9dff`
- Meaning: branch-creation baseline for deepen-i only. It is **not** a release
  tag, compatibility snapshot, governor signature, or proof that 1.0 is
  certified. A later certified 1.0 pin supersedes it; 1.0 wins conflicts.

## Package stubs — freeze readiness

| Stub ID | Theme | FR stubs reviewed | Schema sketch frozen | INV documented | Freeze |
|---|---|---|---|---|---|
| AS-2.0-FED-001 | Multi-vault federation | [ ] **NO** | [ ] **NO** | [ ] **NO** | [ ] **NO** |
| AS-2.0-UX-001 | Advanced Command Center | [ ] **NO** | [ ] **NO** | [ ] **NO** | [ ] **NO** |
| AS-2.0-PROV-001 | Provider adapters | [ ] **NO** | [ ] **NO** | [ ] **NO** | [ ] **NO** |
| AS-2.0-SYNC-001 | Estate sync v2 | [ ] **NO** | [ ] **NO** | [ ] **NO** | [ ] **NO** |
| AS-2.0-COMPAT-001 | Compatibility snapshot consumer | [ ] **NO** | [ ] **NO** | [ ] **NO** | [ ] **NO** |
| AS-2.0-AGENTOS-001 | Agent OS envelope | [ ] **NO** | [ ] **NO** | [ ] **NO** | [ ] **NO** |
| AS-2.0-KCI-001 | KCI | [ ] **NO** | [ ] **NO** | [ ] **NO** | [ ] **NO** |
| AS-2.0-TWIN-001 | Digital Twin | [ ] **NO** | [ ] **NO** | [ ] **NO** | [ ] **NO** |
| AS-2.0-CTX-001 | Context packs | [ ] **NO** | [ ] **NO** | [ ] **NO** | [ ] **NO** |
| AS-2.0-OBS-UX-001 | Obsidian non-canonical UX | [ ] **NO** | [ ] **NO** | [ ] **NO** | [ ] **NO** |

## Cross-cutting freeze gates

| # | Gate | Status |
|---|---|---|
| C1 | Threat register reviewed vs first 2.0 wave (T-2.0-xxx) | [ ] **NO** |
| C2 | Open questions OQ-001…019 answered or deferred with waiver | [ ] **NO** |
| C3 | Fixture families named + harness policy agreed | [ ] **NO** |
| C4 | Prototype artifacts remain marked non-production | [ ] **NO** (inventory exists; freeze not claimed) |
| C5 | No dependency-bearing 2.0 schemas in package data | [ ] **NO** (policy holds; freeze not claimed) |
| C6 | DEPENDENCY-DAG tip pin matches certified 1.0 snapshot | [ ] **NO** |
| C7 | WEB APPLICATION ACCEPTED (blocks UX freeze path) | [ ] **NO** |
| C8 | ESTATE PILOT PASSED or fixture-only waiver recorded | [ ] **NO** |

## Per-stub review notes (deepen-f; none frozen)

These notes make the eventual freeze review inspectable. They are sketches,
not schemas, accepted requirements, or evidence that any row above is green.

### AS-2.0-FED-001

- **FR review sketch:** explicit operator join; identity ambiguity quarantine;
  read-only federation projection; deterministic inventory and conflict output.
- **INV candidates:** `INV-2.0-FED-001` no implicit vault membership;
  `INV-2.0-FED-002` no cross-vault canonical write; `INV-2.0-FED-003`
  ambiguous identity never resolves by ordering or path name.
- **Schema sketch boundary:** a future `federation-join-request` would separate
  declared members, identity pins, operator authorization reference, and
  requested read capabilities. Signature algorithm, canonical encoding, and
  trust-root fields remain blocked by OQ-001/OQ-016. No schema file exists.

### AS-2.0-UX-001

- **FR review sketch:** consume-only view model; explicit source/staleness;
  derived graph and absent-health states cannot be presented as canonical.
- **INV candidates:** `INV-2.0-UX-001` UI state is never authority;
  `INV-2.0-UX-002` graph projection is labelled derived;
  `INV-2.0-UX-003` missing evidence renders unknown, not healthy.
- **Schema sketch boundary:** a future `command-center-read-model` would carry
  source adapter, source snapshot pin, freshness state, mode payload, and
  non-authoritative labels. It must not contain acceptance or canonical-write
  fields. WEB acceptance evidence format remains blocked by OQ-007/OQ-017.

### AS-2.0-PROV-001

- **FR review sketch:** optional adapter lifecycle; deny-by-default tools;
  redaction, provenance, and validation before any canonical consumer.
- **INV candidates:** `INV-2.0-PROV-001` provider disabled leaves Core usable;
  `INV-2.0-PROV-002` raw output stays quarantined; `INV-2.0-PROV-003` remote
  tool discovery cannot expand write capability.
- **Schema sketch boundary:** future `provider-result-envelope` and
  `provider-deny-receipt` would distinguish opaque/redacted result metadata,
  provider/model pin, tool-set digest, provenance references, validation
  state, and denial reason. Raw secrets and promote instructions are forbidden.

### AS-2.0-SYNC-001

- **FR review sketch:** deterministic plan-before-apply; tombstone and
  retention semantics; conflict review; recovery receipt; queue replay rules.
- **INV candidates:** `INV-2.0-SYNC-001` no apply without a pinned plan;
  `INV-2.0-SYNC-002` unresolved conflicts cannot enter promote;
  `INV-2.0-SYNC-003` retries are idempotent for the same operation identity.
- **Schema sketch boundary:** future `sync-plan`, `sync-operation`, and
  `sync-recovery-receipt` would separate desired deltas, preconditions,
  operation identity, queue state, and terminal outcome. Tombstone precedence,
  retry expiry, and cancellation authority remain open.

### AS-2.0-COMPAT-001

- **FR review sketch:** consume a governor-published 1.0 snapshot; reject hard
  drift; make migrations reversible and attributable.
- **INV candidates:** `INV-2.0-COMPAT-001` no unpinned 1.0 contract use;
  `INV-2.0-COMPAT-002` snapshot mismatch fails closed;
  `INV-2.0-COMPAT-003` 1.0 wins every dependency conflict.
- **Schema sketch boundary:** a future `compatibility-snapshot-reference`
  would bind commit, tree, release tag, manifest digest, issuer, and signature
  reference. The observed prep pin is not a certified snapshot.

Each FR/INV/schema review result remains `[ ] NO` until a governor records
the missing decision and evidence. `ATLAS_2_0_IMPLEMENTATION_READY = NO`.


## Freeze-review evidence ledger (deepen-g; all NO)

The ledger separates writing a candidate from accepting it. A future reviewer
must cite durable evidence for every cell; prose in this prep tree is not that
evidence.

| Stub | FR decision still required | INV falsification review still required | Evidence absent now | Status |
|---|---|---|---|---|
| AS-2.0-FED-001 | approve consent, membership, and projection scope | prove ambiguous/unsigned/reordered joins cannot select authority | issuer/verifier decision, certified snapshot, executable negatives | [ ] **NO** |
| AS-2.0-UX-001 | approve read-model modes and freshness semantics | prove route/sample/derived graph cannot stamp acceptance or authority | WEB acceptance bundle and live-vault criteria | [ ] **NO** |
| AS-2.0-PROV-001 | approve adapter lifecycle, quarantine exit, and tool capability scope | prove disabled-provider, secret, missing-pin, and tool-drift cases fail closed | sandbox decision, receipt decision, executable deny cases | [ ] **NO** |
| AS-2.0-SYNC-001 | approve plan/apply/recovery states and tombstone precedence | prove replay, stale winner, cancellation, and partial failure cannot silently promote | authorization/expiry decisions and authentic estate evidence | [ ] **NO** |
| AS-2.0-COMPAT-001 | approve snapshot reference and drift classes | prove forged, stale, mismatched, and conflicting pins fail closed | governor-published 1.0 release snapshot | [ ] **NO** |

## FR / INV review rules (candidate, not frozen)

1. **FR completeness:** each FR must identify actor, input class, observable
   outcome, rejection outcome, and 1.0 dependency. Missing rejection behavior
   keeps `FR stubs reviewed = NO`.
2. **INV testability:** each INV must name at least one falsifying scenario and
   deterministic oracle. Restating an FR as an INV earns no freeze credit.
3. **Boundary consistency:** FED/UX/PROV/SYNC outputs must not imply canonical
   authority, acceptance, authorization, or pilot status.
4. **Open-question discipline:** OQ-001…019 remain unanswered; candidate options
   cannot be copied into FR/INV text as decisions.
5. **Evidence discipline:** narrative, prototype, and reserved fixture names are
   prep evidence only. They cannot satisfy review, schema-freeze, or READY rows.

Every rule above awaits governor review. Every package row and precondition
remains `[ ] NO`; `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

## Explicit non-claims

- All rows above are **unchecked / NO**.
- `ATLAS_2_0_IMPLEMENTATION_READY = NO`.
- Contract freeze ≠ IMPLEMENTATION READY; both require governor action.
- Track B may deepen stubs under `docs/atlas-2.0/**` only — never `src/`.

## Related artifacts

- [PACKAGE-CONTRACT-STUBS.md](PACKAGE-CONTRACT-STUBS.md)
- [COMPATIBILITY.md](COMPATIBILITY.md)
- [IMPLEMENTATION-READY-GATE.md](IMPLEMENTATION-READY-GATE.md)
- [Z-WAVE-INDEX.md](Z-WAVE-INDEX.md)

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | deepen-e: initial checklist; all items unchecked / NO |
| 2026-08-09 | deepen-f: per-stub FR/INV/schema review sketches; all freeze rows remain unchecked / NO |
| 2026-08-09 | deepen-g: evidence ledger and FR/INV review rules; all rows remain NO |
