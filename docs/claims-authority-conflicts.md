# Claims, Authority and Conflicts

AS-CORE-003 turns source observations and validated agent evidence into
explicit, source-backed knowledge. Every emitted claim has provenance and a
durable source lineage when produced from an ingested document. Event evidence
retains its receipt-backed package provenance.

## Identity and lifecycle

Claim IDs do not contain current paths. The semantic identity inputs are the
project identity, durable `source_lineage_id`, claim type, field, and stable
observation locator. A rename or directory move therefore preserves claim
identity; a new retired-slot lineage creates a separate claim namespace. Text
changes retain the logical claim ID and are classified through the persisted
claim lifecycle rather than silently colliding.

The supported lifecycle vocabulary remains `new`, `unchanged`, `updated`,
`superseded`, `contradicted`, `stale`, `removed-source`, `restored`, and
`rejected`. Staleness remains policy-dependent and has no wall-clock default.

## Authority and review

Authority is deterministic: explicit project manifests are primary; validated
execution is next; maintained documentation follows; generated and inferred
evidence remain lower authority. Lower-authority evidence is retained when it
conflicts. Review queues are emitted under `review/conflicts/` and
`review/pending/`; lifecycle state is under `state/claim-lifecycle/`.

## Conflicts

Materially incompatible values create unresolved conflict records keyed by
project, governed field, durable source lineages, and normalized values. Claim
IDs, lineage IDs, evidence references, and authority data remain visible. A
path change alone neither creates nor resolves a conflict, and replay does not
duplicate conflict records.

## Transaction boundary

The compiler returns validated records and rendered content. It performs no
canonical file writes. Ingestion adds all claim, concept, lifecycle, review,
conflict, projection, and receipt outputs to the established write plan; the
existing single promotion boundary remains authoritative. Invalid semantic
state fails before promotion and preserves the prior Vault.

## Deferred work

Richer Claim and Concept population, extraction of multiple field labels on one
line, broader semantic continuity policy, and independent certification remain
outside this implementation handoff.
