# AS-OBSIDIAN-CAPTURE-001-F10 — graph must not write what canonical refuses

**Status:** implemented, awaiting independent verification. **Not sealed.**

## The defect

Two generated-span-preserving writers disagreed on *whether* a document was safe
to write — not on how to describe a refusal, which was F9, but on the refusal
itself. That is a policy difference at a writer boundary.

Reproduced on current `main` (`dbf8d838`) by sweeping **both** sides of the
merge, which is what makes it visible: a corpus varying only the prior note
cannot see a defect that lives on the rendered side.

    existing = <GS>|<GE>|                    (a generated span, no HUMAN regions)
    rendered = <END HUMAN>|<BEGIN HUMAN>|    (markers in reversed order)

    canonical : REFUSE  malformed-protected-markers:unpaired:notes
    graph     : ACCEPT  and writes the document verbatim

## Why it happened

`graph_projections._merge_protected_regions` keeps a historical contract for a
prior note with **no HUMAN regions**: preserve the text outside the generated
span, where the canonical core returns the fresh render and discards it. That
branch splices by hand rather than delegating, so it never reaches the canonical
structural parse.

The validation it does run compares HUMAN marker **counts and names** — never
**order**:

    begins = _HUMAN_BEGIN.findall(text)
    ends   = _HUMAN_END.findall(text)
    if len(begins) != len(ends): refuse
    if sorted(begins) != sorted(ends): refuse

For `END notes` followed by `BEGIN notes` that is one begin and one end with
matching names, so it passes. The canonical core refuses the same document as
`unpaired`, because it parses structure rather than counting tokens.

**Both public validators pass these shapes.** `validate_protected_markers`
accepts reversed and crossed markers on either side; canonical only refuses
later, inside `merge_protected_regions`. So this was never a validator
asymmetry — it was a *path* asymmetry, and that is why counting-based reasoning
missed it.

## The fix

The branch now runs the canonical structural check on the rendered document —
`reject_ambiguous_region_identity`, already public — translating
`ProtectedRegionError` to `GraphProjectionError` at the boundary as the rest of
the module does. Four lines plus an import.

## Measured

Differential sweep varying both sides, on `main` before and after:

| | pairs | divergences | fail-open (canonical refuses, graph accepts) |
|---|---|---|---|
| before, depth 2 | 625 | 3 | **1** |
| after, depth 2 | 625 | 2 | **0** |
| after, depth 3 | 15,625 | 12 | **0** |

Every divergence that remains is the opposite direction — canonical accepts,
graph refuses — which is **F4's disclosed and intentional contract**: graph
refuses rather than silently discard the text outside the generated span. A test
asserts that asymmetry survives, so nobody removes it while "fixing the
asymmetry" wholesale.

## Negative control

Removing the structural check fails **5 of 9** tests, including the differential
sweep. Restored, 9 pass and the source is byte-identical.

`unclosed-region` fails **either way** — graph's count check already catches an
unmatched BEGIN — so the fix specifically closes **reversed** and **crossed**
markers. Recorded because a control that fails for a reason the fix did not
provide is not evidence for the fix.

## Blast radius, stated honestly

The rendered document is **Atlas-generated**, so reaching this needs the
renderer itself to emit malformed markers, which it does not today. This is
defence in depth at a writer boundary rather than a live corruption path.

It is worth closing anyway, and the reason is specific: the canonical core
already refuses these shapes. A second writer that accepts them means the
guarantee depends on which surface reaches the note — the same class of defect
F9 closed for diagnostics, here for policy.

## What is not claimed

- **Not that a live corruption path was found.** It is unreachable through the
  real renderer today.
- **Not that the two surfaces now agree in all directions.** They deliberately
  do not: F4's disclosed contract is intact and asserted.
- **Not that `ingestion.py` is covered.** It is a third writer, owner-gated
  behind a frozen surface, and untouched here.
