# ADR-007 — Claim Identity v2 canonicalization

**Status:** accepted for implementation
**Date:** 2026-08-04
**Work package:** AS-CORE-003
**Author:** Project Atlas Core

## Context

AS-CORE-003 introduced Claim Identity v2 to make project and source lineage
part of the claim identity formula, replacing the v1 identity that depended
only on the normalized claim value. The original v2 implementation used a
pipe-delimited string:

```text
v2|{project_identity}|{source_identity}|{claim_type}|{field}|{locator}
```

This formula is deterministic but not collision-free: any component that can
contain the `|` delimiter (e.g., a project identity, source lineage id, or an
explicit `{#id}` locator) can be arranged to produce the same composite key as a
different set of components. F-001 records this identity-serialization ambiguity.

A second finding, F-002, concerned the v1-to-v2 migration alias map. Ambiguous
mappings — cases where a single v1 claim id maps to more than one v2 claim id
because the semantic locator changed over time — were recorded in the
`ambiguous` collection, but the same records also appeared in the `aliases`
collection. That violates the invariant that a mapping is either resolved or
ambiguous, never both, and enables a downstream consumer to treat an ambiguous
mapping as if it were a canonical promotion.

Finally, the compiler and the migration each maintained its own copy of the
line-extraction rules (`_LINE_RULES`), locator-resolution logic, and
supersession rule. Without a shared definition, future rule changes could cause
the migration to reconstruct v2 identities that the compiler would never emit.

## Decision

1. **Canonical identity serialization.** Replace the pipe-delimited v2 key
   with a compact JSON array serialized by `json.dumps(..., separators=(",", ":"))`.
   The array order is fixed: `["v2", project_identity, source_identity,
   claim_type, field, locator]`. JSON array boundaries make embedded delimiters
   in any component structurally unambiguous.

2. **Shared rules module.** Introduce `project_atlas.claim_identity` as the
   single source of truth for:
   - `_LINE_RULES` (claim-type regex rules and normalized field names)
   - `_SUPERSESSION_RULE`
   - `_slug()` and `_digest()` helpers
   - `canonical_identity_key()`, `claim_id_from_key()`, `v2_claim_id()`
   - `resolve_locator()` and `extract_claims()`

   Both `project_atlas.knowledge_compiler` and
   `project_atlas.migrations.claim_v2_migration` import from this module.

3. **Ambiguous alias invariant.** In the migration, candidates are grouped by
   `v1_claim_id`. If a v1 id maps to exactly one v2 id, one resolved alias is
   emitted. If it maps to multiple v2 ids, every distinct candidate is placed
   in the `ambiguous` collection and none are placed in `aliases`.

4. **Source-lineage normalization.** Cross-platform checkout policy must not
   change durable source identity. For all supported text extensions
   (`.md`, `.txt`, `.json`, `.yaml`, `.yml`, `.toml`, `.html`), discovery and
   validation normalize CRLF sequences to LF before computing the SHA-256 used
   for source identity and provenance hash checks. Binary files are hashed
   as-is.

## Consequences

- F-001 is closed: no real-world component can make two different identity
  tuples collide.
- F-002 is closed: ambiguous mappings are excluded from the resolved alias set.
- Rule-table parity is enforced at import time; the compiler and migration share
  the same extraction and identity logic.
- Re-running the pipeline on a Windows checkout produces the same source
  lineage ids as on a Linux/macOS checkout.
- Existing claim ids change because the canonical key and source hashes are
  different from the previous pipe-delimited/raw-byte versions. Golden
  fixtures for K-004 and K-005 must be regenerated and certified with the new
  candidate.

## Rejected alternatives

- Length-prefixed encoding: equally collision-free, but less inspectable and
  harder to reproduce in non-Python consumers.
- Keeping raw-byte source hashes: rejected because `.gitattributes`
  `* text=auto eol=lf` already commits to LF canonicalization; making identity
  depend on working-tree bytes would make checkout policy part of the identity
  model.
- Separate ambiguous/resolved schema fields: rejected in favor of the simpler
  mutually-exclusive collection invariant already present in the schema.

## Relationship to AS-CORE-003

This ADR amends the AS-CORE-003 Claim Identity v2 remediation. The candidate
that carries this ADR supersedes any prior candidate that lacks the canonical
serialization and source-lineage normalization decisions.
