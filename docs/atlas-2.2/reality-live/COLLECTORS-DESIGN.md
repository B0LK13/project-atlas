# Live Reality Gap — collectors design

Package: **AS-2.2-REALITY-LIVE-001** (PREP)  
Status: architecture / contracts / fixtures — **no runtime wiring yet**

## 1. Goals

1. Collect plane-local evidence that can be compared to declared maturity.
2. Emit a deterministic, schema-valid **derived** gap report.
3. Fail closed on PILOT invent, path escape, secret echo, and authority leak.
4. Remain offline-capable using fixture corpora before authentic estate exists.

## 2. Components

| Component | Role | PREP artifact |
|---|---|---|
| `ConversationalCollector` | Inventory dialogue evidence refs | fixtures + contract |
| `DocumentaryCollector` | Inventory doc/board claims | fixtures + contract |
| `ImplementationCollector` | Inventory code/CLI/test surfaces | fixtures + contract |
| `OperationalCollector` | Inventory runtime receipt signals | fixtures + contract |
| `RealityGapAggregator` | Merge plane reports → gap report | schema draft |
| `RealityGapUI` (later) | Read-only panel over live report | supersedes 2.0 UI catalog |

Proposed future modules (post-unlock only; **not** created in PREP):

- `project_atlas.reality_live` (collectors + aggregator)
- schemas: `reality-live-plane-report`, `reality-live-gap-report`

## 3. Collector contract (shared)

Every collector accepts a **read plan** and returns a **plane report**.

```text
ReadPlan
  vault_root: Path                 # resolved; fail if unsafe
  mode: fixture | live-read-only
  include_globs: list[str]
  exclude_globs: list[str]
  max_files: int                   # hard cap
  allow_pilot_invent: const false

PlaneReport
  plane_id: conversational|documentary|implementation|operational
  evidence_class: fixture-only | live-read-only
  authentic_estate: false | (owner-gated true later)
  invent_pilot_roots: const false
  observations: list[Observation]
  maturity_signals: list[MaturitySignal]
  findings: list[Finding]          # local plane findings only
  generated.by: project-atlas      # no generated.at (NFR-001)
```

### Observation

| Field | Notes |
|---|---|
| `observation_id` | Stable slug |
| `source_ref` | Relative path or receipt id |
| `content_hash` | SHA-256 of normalized bytes when applicable |
| `signal` | Controlled vocabulary token |
| `notes` | Optional short note (no secrets) |

### MaturitySignal

| Field | Notes |
|---|---|
| `surface` | e.g. `api`, `mcp`, `web`, `sched`, `l3`, `oai-import` |
| `observed_class` | Maturity vocabulary |
| `support_level` | `none` · `weak` · `strong` |
| `anchors` | Evidence refs backing the signal |

## 4. Plane collectors

### 4.1 ConversationalCollector

**Inputs (examples):**

- OpenAI export quarantine fixtures / real export paths (read-only)
- Agent session receipts under control-plane routing (consume-only)
- Ask Atlas / ChatGPT bridge capture notes

**Signals:**

- `dialogue_present` · `export_quarantined` · `session_receipt_ok`
- `llm_authority_attempt` (finding if model text treated as claim authority)

**Fail-closed:**

- Refuse absolute / `..` / backslash source paths outside vault
- Redact secret findings to metadata-only
- Never promote dialogue into Layer B

### 4.2 DocumentaryCollector

**Inputs:**

- `docs/atlas-2.1/PACKAGE-BOARD.md`, `FEATURE-MATURITY-MATRIX.md`, `KNOWN-GAPS.md`
- Package cards `docs/AS-2.*.md`
- Strategy gap register rows

**Signals:**

- `board_claim` · `matrix_class` · `gap_row_status` · `release_blocking_flag`

**Fail-closed:**

- Missing board → `UNKNOWN` observations, not invented CLOSED
- Does not rewrite docs

### 4.3 ImplementationCollector

**Inputs:**

- Module inventory (`api_server`, `mcp_*`, `scheduler_*`, `autonomy_*`, …)
- Schema package names
- Test markers / ADV suite presence

**Signals:**

- `module_present` · `live_server_present` · `fixture_harness_only`
- `write_enabled_false` · `deny_by_default`

**Fail-closed:**

- Docstring “production” wording ignored when code path is fixture/dry-run
- Prefer executable proof (importable module + tests) over marketing names

### 4.4 OperationalCollector

**Inputs:**

- `generated/ops/**` receipts when present
- API/MCP/sched/L3 live receipt adapters
- Health / OBS snapshots

**Signals:**

- `receipt_present` · `receipt_empty_honest` · `host_gate_deny`
- `sched_armed` · `l3_disabled` · `authz_cap_hit`

**Fail-closed:**

- Empty ≠ healthy (`Unknown ≠ healthy`)
- DEMO/FIXTURE mode cannot raise authentic estate maturity

## 5. Aggregator

```text
for each surface in declared_board_surfaces:
  claimed = documentary.maturity(surface)
  impl    = implementation.maturity(surface)
  ops     = operational.maturity(surface)
  conv    = conversational.support(surface)   # never sole certifier

  observed = min_rank(impl, ops)              # conservative
  if claimed.rank > observed.rank:
      emit maturity-overclaim
  if claimed and observed == ABSENT/UNKNOWN:
      emit claim-without-evidence
  if ops and documentary missing:
      emit evidence-without-claim
  if conv asserts LIVE_PRODUCTION alone:
      emit authority-leak
```

Rank order (low→high, illustrative):

`ABSENT < UNKNOWN < DOCUMENTATION_ONLY < FIXTURE_ONLY < CONTRACT_ONLY <
PROTOTYPE < STUB < DRY_RUN < DISABLED < BOUNDED < LIVE_READ_ONLY <
LIVE_PRODUCTION`

## 6. Output report (draft)

See schema draft:
`docs/atlas-2.2/contracts/reality-live/reality-live-gap-report.schema.draft.json`

Vault target (post-unlock): `generated/ops/reality-live-gap-report.json`

Truth boundary string (const):

```text
REALITY-LIVE GAP REPORT ≠ PILOT PASS / ≠ WEB ACCEPTED / ≠ RELEASE CERT / ≠ Layer B
```

## 7. Determinism & performance

- Streaming SHA-256 for file observations (NFR-005)
- JSON `sort_keys=True`; no wall-clock in generated payloads (NFR-001)
- Stable sort of observations by `(plane_id, observation_id)`
- Hard `max_files` / size caps per collector

## 8. Adversarial cases (for later ADV pack)

| Case | Expected |
|---|---|
| Path traversal in source_ref | reject / quarantine finding |
| Secret-bearing conversational export | metadata-only; no echo |
| Board claims LIVE_API with only registry module | `maturity-overclaim` |
| Ops empty with docs LIVE | `claim-without-evidence` or overclaim |
| `allow_pilot_invent=true` | constructor reject |
| Conversational-only LIVE_PRODUCTION claim | `authority-leak` |
| Malformed markers / unbalanced protected regions | leave files untouched; non-zero |

## 9. Implementation unlock checklist

- [ ] `v2.1.0` certified / `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- [ ] Promote schema drafts into `src/project_atlas/schemas/`
- [ ] Implement `project_atlas.reality_live` collectors + aggregator
- [ ] Wire read-only CLI or ops report hook (no canonical writes)
- [ ] ADV suite for §8 cases
- [ ] Optional UI catalog deepen (read-only)

## 10. Explicit PREP non-work

- No edits to `src/project_atlas/reality_gap.py` / `reality_gap_ui.py`
- No changes to Core authority / knowledge_compiler semantics
- No authentic PILOT invent / waiver
