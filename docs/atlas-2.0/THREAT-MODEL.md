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

## Mitigation themes (not yet implemented)

1. **Read-first web** — all 2.0 operator surfaces inherit ADR-008 triple invariant.
2. **Federation fail-closed** — ambiguous vault identity → quarantine, never merge-by-guess.
3. **Provider quarantine lane** — adapter output never bypasses provenance or validation.
4. **Compatibility snapshot gate** — 2.0 production branches require published 1.0 snapshot pin.

## Open threat research (prep)

- Federation trust model: operator-signed join manifests vs implicit discovery.
- Provider adapter sandbox: subprocess vs in-process; secret egress boundaries.
- Estate sync conflict resolution: tombstone vs authority winner semantics.

No production branches for threat mitigations until `ATLAS_1_0_RELEASE_CERTIFIED`
and `ATLAS_2_0_IMPLEMENTATION_READY`.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | Initial seed threats |
| 2026-08-09 | Structured register + mitigation themes (prep deepen) |
