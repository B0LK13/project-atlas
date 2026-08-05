# AS-CORE-003 — Claims, Authority and Conflict Processing

Status: implementation complete; governor review required.

Certified base: `e5b9aa8b700afe828cb424503ced84abf37c71ea`

This integration reuses the bounded Claims, Concept, Provenance, Authority,
Review, Conflict, and lifecycle models from the preserved AS-CORE-003 work and
connects them to the AS-ID-001 source registry. Canonical claim identity is
based on project identity, `source_lineage_id`, claim type, field, and semantic
locator. (See [Claim Identity v2 Amendment](AS-CORE-003-claim-identity-amendment.md) for updated v2 semantic locator definitions). Mutable paths and compatibility `source_id` values are descriptive
only.

The existing Core write plan remains the sole promotion boundary. Knowledge
state, projections, reviews, conflicts, lifecycle records, and claim receipts
are rendered into that plan before promotion. The implementation does not
modify AS-ID-001 genesis, lineage allocation, source lifecycle vocabulary, or
the Control Plane.

The old AS-CORE-003 candidate refs (`04a62fe`, `49e9a91`, `c120c03`) remain
historical references. Their semantic work was selectively reapplied; their
evidence was not reused as certification evidence.

Remaining review boundary: independent governor review and certification.
