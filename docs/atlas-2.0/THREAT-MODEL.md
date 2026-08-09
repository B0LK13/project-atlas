# Atlas 2.0 — Threat model (prep)

Status: **PREP ONLY** — `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

Structured threat inventory for 2.0 planning. Mitigations listed here are
**design intent** only; no new production controls land under Track B.

## Scope boundary

| In scope (prep) | Out of scope (Track B) |
|---|---|
| Threat identification + mitigation sketches | Production code / CLI changes |
| Cross-reference to 1.0 ADRs and contracts | New runtime enforcement |
| Federation / provider / sync threat seeds | Dependency-bearing schemas |

## Threat register

| ID | Threat | Asset / surface | Likelihood | Impact | Mitigation (prep) | 1.0 carry-over |
|---|---|---|---|---|---|---|
| T-2.0-001 | Path traversal via federation join paths | Vault filesystem, ingest writes | M | H | Reuse AT-013 `_inside()` / `safe_relative_component`; fail-closed on resolved paths | `ingestion.py`, `scaffold.py` |
| T-2.0-002 | Secret leakage in provider adapter output | Generated notes, logs, receipts | M | H | Reuse NFR-004 / `secrets.scan_text`; quarantine before promote | `secrets.py`, ingest quarantine |
| T-2.0-003 | UI-as-truth — browser state promoted to canonical | Web shell, Command Center | M | H | ADR-008 invariants; read-only `web_api`; UI≠canonical banners | ADR-008, AS-WEB-001 |
| T-2.0-004 | Graph-as-authority — derived edges pick winners | Impact lens, relationship store | M | H | Graph≠authority; consume-only projections; no graph→claims writer | AS-J-005, AS-GRAPH-003 |
| T-2.0-005 | Unknown-as-healthy — absent OBS rendered green | Ops health, estate rollup | M | H | Unknown≠healthy; absent snapshot → `rollup=unknown` | AS-OBS-001, `web_api.health` |
| T-2.0-006 | Skill / policy drift across vaults | Agent control plane, skill manifest | L | H | Skill SHA-256 binding; receipt gate; vault identity lock | AS-CTRL-001, AS-SKILL-001 |
| T-2.0-007 | Multi-vault identity collision | Federation join, global entities | M | H | AS-ID-001 lineage locks; explicit ambiguity fail-closed | `lineage.py`, AS-XPROJ-001 |
| T-2.0-008 | Compatibility snapshot bypass | 2.0 packages on 1.0 vaults | L | H | AS-2.0-COMPAT-001 consumer gate; no silent contract rewrite | COMPATIBILITY.md |
| T-2.0-009 | Provider provenance bypass | Optional model-assisted classification | M | H | Deterministic-first (FR-004); provider output quarantined until validated | FR-004, NFR-006 |
| T-2.0-010 | Cross-estate sync partial write | Estate sync v2, tombstones | M | H | Atomic promote boundary; tombstone + retention policies | AS-INT-010, AS-CORE2-009 |
| T-2.0-011 | Implicit federation discovery without operator-signed join | Multi-vault join, trust boundary | M | H | Require operator-signed join manifests; quarantine unsigned discovery; no merge-by-guess | OQ-001, AS-2.0-FED-001 |
| T-2.0-012 | Provider/MCP adapter secret egress or sandbox escape | Adapter process, logs, tool surface | M | H | Prefer subprocess sandbox sketch; metadata-only secret findings; deny write tools (`promote`, claim mutate) | OQ-004, OPENAI-MCP-DESIGN.md |
| T-2.0-013 | Protected human-region corruption during 2.0 regen paths | OKF notes, human-edit markers | L | H | Reuse AT-011 fail-closed unbalanced markers; byte-identical protected regions on regen | AT-011, FR-015 |
| T-2.0-014 | Estate sync conflict silently promotes tombstone or stale authority winner | Estate sync v2, claims, review queue | M | H | Surface conflicts in review queue; no silent authority overwrite; tombstone vs winner policy explicit before promote | OQ-011, OQ-012, AS-2.0-SYNC-001, AS-CORE-003 |
| T-2.0-015 | MCP / provider tool enumeration drift introduces write-capable tools | Adapter registry, tool allowlist | M | H | Deny-by-default tool allowlist; CI drift check vs pinned deny set (`promote`, claim mutate, vault write); registry version pin | OQ-004, OPENAI-MCP-DESIGN.md, AS-2.0-PROV-001 |
| T-2.0-016 | Compatibility snapshot pin forgery or stale pin acceptance | Release gate, 2.0 package CI | L | H | Require governor-published snapshot (HEAD/TREE/tag); refuse unsigned/stale pins; hard-drift fails CI | OQ-013, COMPATIBILITY.md, AS-2.0-COMPAT-001 |
| T-2.0-017 | Sync queue entry is mistaken for authorization, or replay changes scope | Estate sync queue, apply worker | M | H | Separate requested/planned/authorized states; bind operation identity, plan digest, actor authorization, and replay count before apply | OQ-018, AS-2.0-SYNC-001 |
| T-2.0-018 | Web acceptance is falsely stamped from route availability, sample data, or self-attestation | WEB acceptance gate, UX entry | M | H | Require independently attributable acceptance evidence bound to commit/tree and live-vault criteria; rendering alone proves nothing | OQ-017, AS-WEB-ACCEPT-001, AS-2.0-UX-001 |
| T-2.0-019 | Fixture estate is confused with an authentic pilot estate | Fixture inventory, estate gate | M | H | Label fixture roots and receipts; require explicit evidence class; fixture-only waiver cannot claim ESTATE PILOT PASSED | OQ-019, FIXTURE-PLAN.md |
| T-2.0-020 | A 2.0 draft silently overrides a conflicting 1.0 contract | All package boundaries | L | H | Pin the 1.0 snapshot and apply the 1.0-wins rule; quarantine unresolved drift rather than selecting latest-by-version | COMPATIBILITY.md, DAG.md |
| T-2.0-021 | A read-capable provider or federation component becomes a confused deputy for canonical writes | FED/PROV capability boundary | M | H | Bind capabilities to operation and snapshot; reject delegated or discovered writes; keep consume and promote identities separate | OQ-004, OQ-016, AS-2.0-FED-001, AS-2.0-PROV-001 |
| T-2.0-022 | A valid receipt or authorization is replayed against a different snapshot, plan, or vault | Federation joins, provider results, sync apply | M | H | Bind future receipts to vault identities, snapshot/plan digest, operation identity, and scope; reject context mismatch | OQ-006, OQ-016, OQ-018 |
| T-2.0-023 | Error or deny output leaks secrets, absolute paths, or raw provider content | Logs, quarantine summaries, fixture expected output | M | H | Metadata-only findings; synthetic relative paths in fixtures; redact before formatting errors; review negative payloads | NFR-004, FIXTURE-PLAN.md |
| T-2.0-024 | Resource-amplification input causes unbounded federation inventory, provider tool discovery, or sync plan growth | FED/PROV/SYNC planning surfaces | M | M | Define bounded inventory/tool/plan budgets and fail-closed overflow receipts before production; preserve deterministic truncation semantics | OQ-004, AS-2.0-FED-001, AS-2.0-SYNC-001 |
| T-2.0-025 | Reality-gap doc mistaken for release/PILOT certification | Program governance | L | M | Label PREP; keep RELEASE/PILOT/WEB/READY flags explicit NO | REALITY-GAP.md |
| T-2.0-026 | Obsidian/plugin UX writes canonical vault regions | OKF notes, human markers | M | H | Non-canonical prototype only; protected-region fail-closed; no plugin shipping from prep | OBSIDIAN-2.0.md, AT-011 |
| T-2.0-027 | Migration runner invented before freeze/READY | Vault state, schemas | L | H | Docs-only migration strategy until Phase C/D; no runners in Track B | MIGRATION-STRATEGY.md |
| T-2.0-028 | `2.0_PREP_COMPLETE_PENDING_1.0_ANCHOR` confused with IMPLEMENTATION READY | Track B gate | M | H | Separate status strings; READY requires gates 1–10 including 1.0 anchor | IMPLEMENTATION-READY-GATE.md |

## Mitigation themes (not yet implemented)

1. **Read-first web** — all 2.0 operator surfaces inherit ADR-008 triple invariant.
2. **Federation fail-closed** — ambiguous vault identity → quarantine, never merge-by-guess.
3. **Provider quarantine lane** — adapter output never bypasses provenance or validation.
4. **Compatibility snapshot gate** — 2.0 production branches require published 1.0 snapshot pin.
5. **Evidence-class separation** — queue, web acceptance, fixtures, pilot evidence, and canonical authority are distinct states.

## Open threat research (prep)

- Federation trust model: operator-signed join manifests vs implicit discovery
  (partially captured as T-2.0-011; residual: signed-manifest crypto shape).
- Provider adapter sandbox: subprocess vs in-process; secret egress boundaries
  (partially captured as T-2.0-012; residual: host FS allowlist).
- Estate sync conflict resolution: tombstone vs authority winner semantics
  (partially captured as T-2.0-014; residual: retention archive vs soft tombstone).
- MCP tool enumeration drift: new write-capable tools sneaking past deny list
  (partially captured as T-2.0-015; residual: dynamic tool discovery from remote MCP).
- Snapshot pin authenticity and rotation (partially captured as T-2.0-016;
  residual: multi-snapshot migration windows).
- Sync queue authorization, cancellation, expiry, and replay identity
  (captured as T-2.0-017; policy blocked by OQ-018).
- Independent WEB acceptance evidence and fixture-vs-pilot evidence classes
  (captured as T-2.0-018/019; blocked by OQ-017/OQ-019).
- Capability delegation and receipt context binding (captured as T-2.0-021/022;
  residual: capability token/receipt contract decisions remain open).
- Error-channel redaction and planning resource budgets (captured as
  T-2.0-023/024; residual: limits and deterministic overflow behavior unchosen).

No production branches for threat mitigations until `ATLAS_1_0_RELEASE_CERTIFIED`
and `ATLAS_2_0_IMPLEMENTATION_READY`. Explicit: `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | Initial seed threats |
| 2026-08-09 | Structured register + mitigation themes (prep deepen) |
| 2026-08-09 | Added T-2.0-011…013 (federation trust, adapter egress, protected regions) |
| 2026-08-09 | deepen-e: added T-2.0-014…016 (sync conflict, tool drift, snapshot pin) |
| 2026-08-09 | deepen-f: added T-2.0-017…020 (queue misuse, false web stamp, fixture/pilot confusion, 1.0 conflict) |
| 2026-08-09 | deepen-g: added T-2.0-021…024 (confused deputy, context replay, error leakage, resource amplification); residuals remain open |
| 2026-08-09 | deepen-i: added T-2.0-025…028 (reality-gap stamp, Obsidian write, migration runner, PREP_COMPLETE≠READY); closeout notes — residuals remain design intent |
