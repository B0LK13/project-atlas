# Atlas 2.0 — Package contract stubs (§98 seed)

Status: **PREP ONLY** — names reserved; not authorized for production impl.
`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

| Stub ID | Theme | Notes |
|---|---|---|
| AS-2.0-FED-001 | Multi-vault federation | docs/contracts only |
| AS-2.0-UX-001 | Advanced Command Center | after WEB 1.0 accepted |
| AS-2.0-PROV-001 | Provider adapters | optional; provenance non-bypass |
| AS-2.0-SYNC-001 | Estate sync v2 | after INT-013 / CORE2-010 |
| AS-2.0-COMPAT-001 | Compatibility snapshot consumer | post 1.0 freeze |

## Design deepen (2026-08-09c)

- `DAG.md` — gate chain + package dependency sketch
- `OPENAI-MCP-DESIGN.md` — provider/MCP prep notes (no production wiring)
- Threat model register retained; still PREP ONLY

Do not open production branches for these until `ATLAS_1_0_RELEASE_CERTIFIED`
and `ATLAS_2_0_IMPLEMENTATION_READY`.

## Functional requirement stubs (FR-2.0-xxx)

Draft FR IDs for planning traceability only — **not** certified requirements.

### AS-2.0-FED-001 — Multi-vault federation

| FR ID | Requirement (stub) | 1.0 dependency |
|---|---|---|
| FR-2.0-FED-001 | Join two or more vault roots with explicit operator manifest; no implicit merge | AS-ID-001, AS-XPROJ-001 |
| FR-2.0-FED-002 | Federation join must fail closed on identity ambiguity | `lineage.py` |
| FR-2.0-FED-003 | Cross-vault read lenses are consume-only; no cross-vault promote | ingest `_promote` boundary |
| NFR-2.0-FED-001 | Federation fixtures produce deterministic join inventory (no wall-clock) | NFR-001 |

### AS-2.0-UX-001 — Advanced Command Center

| FR ID | Requirement (stub) | 1.0 dependency |
|---|---|---|
| FR-2.0-UX-001 | Command Center advanced modes consume read adapters only | AS-WEB-001, ADR-010 |
| FR-2.0-UX-002 | Impact lens displays derived graph; never elevates graph to authority | AS-J-005 |
| FR-2.0-UX-003 | All modes preserve UI≠canonical / Graph≠authority / Unknown≠healthy | ADR-008 |
| NFR-2.0-UX-001 | Blocked until WEB APPLICATION ACCEPTED = YES | AS-WEB-ACCEPT-001 |

### AS-2.0-PROV-001 — Provider adapters

| FR ID | Requirement (stub) | 1.0 dependency |
|---|---|---|
| FR-2.0-PROV-001 | Provider adapters are optional; disabling leaves MVP functional | NFR-006 |
| FR-2.0-PROV-002 | Model output quarantined until provenance + schema validation pass | FR-004, ingest quarantine |
| FR-2.0-PROV-003 | No provider path bypasses `secrets.scan_text` | NFR-004 |
| NFR-2.0-PROV-001 | Adapter registry documents skill/version pin per provider | AS-CTRL-001 |

### AS-2.0-SYNC-001 — Estate sync v2

| FR ID | Requirement (stub) | 1.0 dependency |
|---|---|---|
| FR-2.0-SYNC-001 | Incremental sync respects tombstones and retention policy | AS-INT-010, AS-INT-009 |
| FR-2.0-SYNC-002 | Sync conflicts surface in review queue; no silent authority overwrite | AS-CORE-003 |
| FR-2.0-SYNC-003 | Promote recovery boundary preserved on partial failure | AS-CORE2-009 |
| NFR-2.0-SYNC-001 | Blocked until INT-013 / CORE2-010 entry gates green | backlog |

### AS-2.0-COMPAT-001 — Compatibility snapshot consumer

| FR ID | Requirement (stub) | 1.0 dependency |
|---|---|---|
| FR-2.0-COMPAT-001 | 2.0 packages declare consumed 1.0 snapshot (HEAD/TREE/tag) | COMPATIBILITY.md |
| FR-2.0-COMPAT-002 | Contract drift against snapshot fails CI, not runtime guess | schema validation |
| FR-2.0-COMPAT-003 | Migration tooling produces reversible audit trail | INT-012 (open) |
| NFR-2.0-COMPAT-001 | No production impl until `ATLAS_1_0_RELEASE_CERTIFIED` | release gate |

## Candidate package boundaries (deepen-f; non-normative)

The terms **IN**, **OUT**, and **FORBIDDEN** describe review boundaries only.
They do not establish Python APIs, JSON Schemas, or runtime semantics.

### FED boundary

- **IN:** operator-declared member references; AS-ID-001 identity pins;
  compatibility snapshot references; consume-only project/entity projections.
- **OUT:** deterministic membership inventory; ambiguity/conflict records;
  read-only federation lens with source-vault attribution.
- **FORBIDDEN:** directory crawling as consent; path-name identity; implicit
  merge; cross-vault `_promote`; choosing an authority winner from graph rank.

### UX boundary

- **IN:** versioned read-adapter results; health state with unknown preserved;
  derived impact projection; evidence and freshness references.
- **OUT:** display-only mode models; source/staleness labels; explicit blocked,
  degraded, and unknown states; operator navigation intent.
- **FORBIDDEN:** canonical writes; acceptance inferred from routes rendering;
  graph-derived authority; sample/fixture data labelled as live estate state.

### PROV boundary

- **IN:** redacted request metadata; provider/model/config pins; deny-by-default
  tool capability declaration; source context references, never hidden writes.
- **OUT:** quarantined result envelope; provenance references; validation and
  secret-scan state; deterministic denial receipt for forbidden capabilities.
- **FORBIDDEN:** raw credential persistence; direct vault mutation; claim or
  authority promotion; dynamic MCP tools gaining capability without re-review.

### SYNC boundary

- **IN:** pinned source/destination identities; compatibility pins; prior sync
  cursor; tombstone/retention facts; explicit operator scope.
- **OUT:** deterministic dry plan; operation queue records; conflict-review
  entries; apply/recovery receipts that distinguish planned/applied/terminal.
- **FORBIDDEN:** enqueue-as-authorization; duplicate replay with a new identity;
  silent stale/tombstone winner; fixture-estate evidence treated as pilot proof.

Cross-package rule: where any candidate 2.0 boundary conflicts with the 1.0
snapshot, **1.0 wins**. All boundary names remain subject to freeze review.
`ATLAS_2_0_IMPLEMENTATION_READY = NO`.


## Candidate interaction and rejection notes (deepen-g; non-normative)

These notes deepen review vocabulary only. They are not API definitions,
serialized records, lifecycle decisions, or production schemas.

### FED interaction sketch

- **Candidate phases:** declare members → verify identity/snapshot references →
  evaluate consent/ambiguity → publish consume-only inventory or quarantine.
- **Rejection classes to review:** unsigned member, duplicate lineage identity,
  incompatible snapshot, path outside declared root, capability beyond read.
- **Authority firewall:** inventory inclusion means discoverable membership only;
  it does not select a canonical project, claim, entity, or source.
- **Unresolved:** issuer/verifier, signature form, namespace policy, and trust-root
  rotation remain OQ-001/OQ-002/OQ-003/OQ-016.

### UX interaction sketch

- **Candidate phases:** read pinned adapter snapshot → classify freshness/evidence
  state → derive labelled view → render blocked/degraded/unknown explicitly.
- **Rejection classes to review:** absent source pin, unsupported view version,
  unlabeled derived graph, fixture presented as live, stale state presented fresh.
- **Acceptance firewall:** rendering, route availability, and sample-data success
  are observations only; none can emit WEB APPLICATION ACCEPTED evidence.
- **Unresolved:** rollout, live-vault default, impact sources, and independent
  acceptance evidence remain OQ-007/OQ-008/OQ-009/OQ-017.

### PROV interaction sketch

- **Candidate phases:** resolve pinned adapter/capabilities → redact request
  metadata → execute in selected isolation boundary → quarantine result → scan,
  provenance-check, and validate → expose only an accepted consume-only result.
- **Rejection classes to review:** unpinned model/tool set, capability drift,
  secret finding, incomplete provenance, invalid result, write-capable discovery.
- **Promotion firewall:** successful provider execution is not claim acceptance,
  source authority, or permission to call canonical writers.
- **Unresolved:** isolation boundary, deterministic precedence, and receipt family
  remain OQ-004/OQ-005/OQ-006.

### SYNC interaction sketch

- **Candidate phases:** inventory pinned endpoints → compute deterministic dry plan
  → classify conflicts/tombstones → obtain separate authorization → apply through
  recovery boundary → issue terminal receipt without erasing prior states.
- **Rejection classes to review:** changed plan digest, expired/cancelled authority,
  replay with changed scope, unresolved conflict, stale resurrection, partial apply.
- **Evidence firewall:** queued/planned/applied/fixture-rehearsed are distinct; none
  alone proves authorization, canonical success, or ESTATE PILOT PASSED.
- **Unresolved:** tombstone policy, rollback/forward-fix, authorization lifetime,
  replay identity, and evidence class remain OQ-011/OQ-012/OQ-018/OQ-019.

### Cross-package review vocabulary

Candidate states such as `declared`, `quarantined`, `derived`, `planned`, and
`denied` are prose labels, not reserved enum values. Any future schema must be
separately proposed and frozen. Failure details must not contain secrets, raw
provider content, or untrusted absolute paths. No package may infer a stronger
governance state from a weaker operational state.

`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

## Prep deepen (2026-08-09d)

- `IMPLEMENTATION-READY-GATE.md` — §101 checklist (READY=NO)
- CHARTER / VISION / PRD rewritten as PROTOTYPE / PREP (not stubs-only)
- Firewall unchanged: no 2.0 production semantics

## Prep deepen (2026-08-09)

Added COMPATIBILITY.md, FIXTURE-PLAN.md, OPEN-QUESTIONS.md — still PREP ONLY.
Expanded FR stubs for federation, UX, provider, sync, compat (this revision).

## Prep deepen-f (2026-08-09)

Added candidate FED/UX/PROV/SYNC IN/OUT/FORBIDDEN boundaries without shipping
schemas or authorizing production packages. READY remains NO.

## Prep deepen-g (2026-08-09)

Added candidate interaction/rejection notes for FED/UX/PROV/SYNC. Open questions remain unresolved; no schema or production contract shipped.
READY remains NO.
