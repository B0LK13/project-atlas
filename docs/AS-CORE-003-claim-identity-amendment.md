# AS-CORE-003: Claim Identity v2 Architecture Amendment

**Status**: Authorized Architecture Amendment
**Context**: Replaces Claim Identity v1 semantics with a durable semantic locator.

## 1. Claim Identity v2
Claim Identity v2 is defined as a cryptographic hash of the following stable components:
`hash(identity_version | project_identity | source_lineage_id | claim_type | normalized_field | stable_semantic_locator)`

## 2. Locator Normalization
To ensure consistent generation of the `stable_semantic_locator`, normalization must follow this exact priority chain:
1. **Explicit ID**: A defined, stable identifier provided directly in the source.
2. **Schema Key**: The primary key or unique constraint field defined by the document schema.
3. **Semantic Anchor**: The nearest stable structural anchor (e.g., a named Markdown heading or explicit block-level semantic anchor). Brittle structural paths, such as AST indices or line numbers, are strictly forbidden.
4. **Fail Closed**: If none of the above can produce a stable locator, the normalization must fail closed, reject the claim, and demand an explicit ID.

## 3. Migration and Alias Semantics
To migrate from v1 to v2:
* **Historical Source Recompilation**: Recompilation must traverse the historical Git tree of the controlled documentation roots. This ensures that all historical v1 claims—including those that have since been deleted, superseded, or rejected—are processed using the v2 identity generator.
* **Durable Compatibility Alias Map**: A durable alias map must be maintained, mapping all active and historical v1 identifiers to their new v2 canonical identities to permanently prevent broken references in preserved receipts.

## 4. Ambiguity Handling
If any step in the ingestion or normalization pipeline encounters ambiguous identity boundaries (e.g., duplicate explicit IDs or colliding semantic anchors), the process must fail closed and quarantine the affected records. Ambiguity must never be resolved by silently dropping or arbitrarily prioritizing conflicting records.

## 5. Zero-Write Behavior
If a recompiled source produces the exact same v2 claim state as currently exists in the canonical projections, the pipeline must execute zero writes. The transaction must complete successfully without modifying the underlying storage or generating new receipts for unchanged claims.

## 6. Idempotency
Claim Identity v2 generation and routing must be strictly idempotent. Repeated application of the same source evidence must always yield the exact same identity hash and document state.

## 7. Rollback and Recovery
If migration or recompilation fails mid-transaction:
* The transaction must be entirely rolled back.
* The system must revert to the last known good v1 state.
* The alias map must not be partially updated.

## 8. Concurrency
To guarantee consistency during multi-agent migration, recompilation, and continuous ingestion, operations must employ Optimistic Concurrency Control (OCC) backed by state revision hashes, or strict repository-level pessimistic locking. If multiple processes attempt simultaneous mutations on overlapping claim state, conflicting or lagging transactions must fail closed, rollback safely, and demand a retry.

## 9. Scope Boundaries
This amendment specifically targets the `project_atlas` Core Vault compiler. It does not alter the Control Plane event capture mechanisms, AS-ID-001 lineage allocation rules, or external Graphify adapters. The amendment is bounded to how claims are uniquely identified and stored within the Atlas Core.

## 10. Evidence Requirements
* **Migration Receipt**: A cryptographic receipt must be generated for the v1-to-v2 migration event.
* **Recompilation Audit**: The alias map must be backed by an audit log showing the v1-to-v2 mapping for the full historical tree.
* Historical evidence receipts from AS-CORE-003 and AS-ID-001 remain immutable and must only be referenced, never rewritten.

## 11. Implementation Acceptance Criteria
* The v2 identity hash function strictly incorporates all 6 required fields.
* The locator normalization priority chain correctly resolves semantic anchors, and fails closed on unresolvable locators by demanding an explicit ID.
* Recompilation of existing and historical fixtures generates zero duplicate claims and correctly populates the alias map.
* **Historical Completeness Test**: The durable alias map correctly resolves historical v1 IDs for claims that no longer exist in the current document state.
* **Concurrency Test**: Concurrent ingestion or migration operations simulating race conditions correctly reject and rollback the lagging transaction.
* Zero-write behavior is demonstrably active during idempotent replays.
* Rollback safely restores the previous state upon injected failure.
