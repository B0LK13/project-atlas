# ADV pool — fixture invariants (PREP)

Status: **PREP**. Applies to any fixture sketch under
`docs/atlas-2.2/adv-pool/fixtures/` and to sibling 2.2 prep fixtures that
this pool references.

## Hard rules

1. **No secret leakage** — fixtures must not contain real API keys, private
   keys, passwords, bearer tokens, connection strings, or AWS-style access
   keys. Use synthetic placeholders such as `sk-test-not-a-real-key` only
   when a negative test needs a *shape*, never a live credential.
2. **Metadata-only findings** — if a fixture models a secret scan hit, record
   detector id / offset / severity only; never the matched substring
   (NFR-004).
3. **No authority elevation** — fixture expected outputs must keep
   `authority_plane` / Layer B flags honest. Retrieval hits, context packs,
   memory entries, KCI greens, DoD proofs, temporal diffs, reality-gap notes,
   and research answers remain non-authoritative unless a separate,
   provenance-backed promote path (out of scope here) says otherwise.
4. **Fail-closed** — negative fixtures must expect reject / quarantine /
   unknown — never silent success on ambiguous identity, path traversal,
   evidence-class mismatch, or missing baselines.
5. **Determinism** — no wall-clock `generated.at` in expected JSON/Markdown
   (NFR-001); prefer `generated.by` only.
6. **Path safety** — only synthetic relative vault paths
   (e.g. `projects/demo/note.md`); no absolute host paths, `..`, or
   backslash traversal (AT-013).
7. **Evidence class** — label `fixture` vs `authentic_pilot` explicitly;
   fixture PASS never implies PILOT PASS or `ATLAS_2_1_RELEASE_CERTIFIED`.

## Checklist for authors

- [ ] No real secrets or PII
- [ ] Negative cases assert fail-closed outcomes
- [ ] Flags `ATLAS_2_1_RELEASE_CERTIFIED=NO` remain true in narrative
- [ ] Does not edit `docs/atlas-2.1/ADV-LIVE-SUITE.md`
- [ ] Does not add `src/` runtime hooks from this package
