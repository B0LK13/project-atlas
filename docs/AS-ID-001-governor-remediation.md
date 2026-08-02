# AS-ID-001 governor remediation

Status: final bounded remediation complete — independent rereview required.

This final remediation starts from reviewed candidate `91cbab5` and preserves
that candidate unchanged. The referenced governor report path was not present in
the checkout or any visible Git ref, so the explicit defect register in the
owner directive was used as the available authoritative input. No architecture
decision was invented where the directive required fail-closed behavior.

The remediation validates v1 continuity chains and rejects missing references,
cycles, contradictory edges, and incomplete history. Registry resolution now
requires unique compatible fingerprint/lineage evidence; deletion alone does
not restore changed content. Ambiguous cases raise a deterministic structured
`unresolved-identity` finding before promotion. Compatibility mirror fields
are formally defined in the v2 schema and domain model. Promotion is followed
by marker, registry, lineage, generation, schema, duplicate-ID, and allocation
receipt verification while the Core lock remains held.

The public CLI race test starts two separate Python processes and proves one
UUID, one allocation receipt, shared observation of the committed identity,
and no lock artifact. AS-CORE-002 and AS-CORE-003 remain outside this branch.

The final bounded remediation adds an explicit lineage-resolution contract,
reachable retired-slot reoccupation with deterministic `max + 1` generation
allocation, restoration and supersession relationship fields, complete
unresolved-identity findings, and ordered migration receipt evidence edges.
The final evidence receipt is
`docs/evidence/AS-ID-001-final-certification-remediation-receipt.yaml`.
