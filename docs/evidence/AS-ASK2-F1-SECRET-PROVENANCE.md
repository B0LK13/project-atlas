# AS-ASK2-F1 — Secret-shaped provenance is not echoed

- Package: `AS-ASK2-F1`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- NFR-004 / AT-014
- MODEL OUTPUT != AUTHORITY

## Finding

Ask Atlas 2 built provenance pointers from `ref` / `source_id` without
`scan_text`. Secret-shaped ids such as `AKIAIOSFODNN7EXAMPLE` were kept
in `EVIDENCE[].provenance[].ref`. D-178/D-181 only covered secret claim
values (ANSWER stays null).

Independently reproduced on live main
`b87b4a226f4aa8b2f669edf112aa3476454f754f`.

## Remediation

Drop secret-shaped refs in `ask2._record_provenance` and
`runtime_22` provenance sanitize. Matched secret material is never
returned.

## Out of scope

- Truth Core writes
- merge authorization

## Validation

See the PR body for commands actually run on the candidate object.
