# AS-OBSIDIAN-CAPTURE-001-F10 — graph must not write what canonical refuses

**Status:** integrated on `main` and **SEALED** (PR #753). See the post-merge seal at the end of this file.

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

**Both validators pass these shapes** -- canonical's public
`validate_protected_markers` and graph's private `_validate_protected_markers`
(an earlier revision called both public; graph's is not); canonical only refuses
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

Removing the structural check fails **4 of 7** tests, including the differential
sweep and the end-to-end brick test. Restored, 7 pass and the source is
byte-identical. Re-measured on the merge object `06362807`; the failing set is
`crossed-a-b`, `reversed-end-before-begin`,
`a_poisoned_field_cannot_brick_the_projection` and
`no_fail_open_divergence_across_a_differential_sweep`.

**An earlier revision of this section said 5 of 9, and 9 passing.** That was
accurate against `4dc35e19`, where the module collected nine cases. It went stale
at `ae5bc6b4` -- the commit that replaced the tautological
`refusal_leaves_the_prior_note_untouched` (three parametrised shapes) with the
single end-to-end `a_poisoned_field_cannot_brick_the_projection`, taking the
module from nine cases to seven. The backlog entry was updated to 4 of 7; this
section was not, and I sealed it in that state. Review caught it.

That is the **fourth** instance in this package of a correction reaching some
copies and not all -- in the record whose own seal narrates that exact pattern.
Recorded rather than silently overwritten, because the pattern is the finding.

`unclosed-region` fails **either way** — graph's count check already catches an
unmatched BEGIN — so the fix specifically closes **reversed** and **crossed**
markers. Recorded because a control that fails for a reason the fix did not
provide is not evidence for the fix.

## Blast radius — I got this wrong, in the direction that understated it

An earlier revision of this receipt said reaching the defect "needs the renderer
itself to emit malformed markers, which it does not today," and called it
defence in depth. **That is false.** Independent verification challenged it and
reproduction settled it.

Nothing in the render path escapes marker text. `_redact_text` strips secrets and
truncates to 240 characters but never touches HTML comments, so a relationship
field containing HUMAN marker text reaches the render **verbatim**. Measured:
**five** fields carry it into the bundle -- `source_entity_id`,
`target_entity_id`, `relationship_type`, `relationship_id`, and
`provenance.graphify_artifact_refs[].relative_path`, which bypasses
`_redact_text` entirely. An earlier revision named only the first four.

**The precondition, which neither my original claim nor verification's stated:**
the prior note must have **no HUMAN regions**, because that is the branch which
splices by hand. An operator who deletes their HUMAN block, or a note predating
HUMAN emission, is in that state. With a note that *does* carry HUMAN regions --
the shape a fresh render produces -- the merge delegates to the canonical core
and is correctly refused even before this fix.

The precondition is **necessary but not sufficient**: verification measured that
of five poison shapes written on the base, only three bricked -- the poison must
also land **inside the generated span**, since the hand-splice carries only that
span across. Relationship record fields land exactly there, so the real vector
does brick; I reproduced it for two shapes through `source_entity_id`.

Given all of that, reproduced end to end through the real writer against a real
vault:

    BASE   poisoned refresh WRITTEN; the note now carries reversed markers;
           every later refresh -- including a clean one with zero
           relationships -- is PERMANENTLY REFUSED. The projection cannot
           self-heal.
    HEAD   refused up front; note byte-identical; no staging residue; the
           projection remains refreshable afterwards.

So this is a **durable denial-of-refresh corruption**, not defence in depth. The
fix converts a permanent brick into a clean refusal. A test now pins that
end-to-end consequence rather than the mechanism.

**Still not claimed:** that an end-to-end `discover -> ingest -> graphify` run
with attacker-controlled sources can plant such a field value. What is shown is
that the render and write layers propagate it unsanitised and that the pre-fix
writer persists the result. The ceiling on reachability is set upstream, and is
not established here.

## What is not claimed

- **Not that upstream reachability is established.** A live corruption path
  *is* demonstrated at the render and write layers -- see Blast radius above --
  but whether a full `discover -> ingest -> graphify` run with attacker-controlled
  sources can plant such a field value is not shown here. An earlier revision of
  this bullet said no live corruption path was found, contradicting the section
  above it in the same file; verification caught it.
- **Not that the two surfaces now agree in all directions.** They deliberately
  do not: F4's disclosed contract is intact and asserted.
- **Not that `ingestion.py` is covered.** It is a third writer, owner-gated
  behind a frozen surface, and untouched here.

## Post-merge seal — `06362807`

Integrated as PR #753. **Merged unrebased at the verified object.**

| | |
|---|---|
| merge commit | `06362807a65412e80506685df12f820ab2d7510a` |
| first parent (base) | `a7adce4ed70ccbd89a8a7936d304db5b37095101` |
| second parent (verified head) | `3b22f6d4a6bc0ea0c18ac6cc83718c4ecc1844fb` |
| merge tree | `1b11d3a0281aa3df5c564d66cac44ba953f9d28e` |
| PR head tree | `1b11d3a0281aa3df5c564d66cac44ba953f9d28e` — **identical** |
| `git diff 3b22f6d4 06362807` | empty |
| component trees | `src 8ec29893`, `tests 6aa392e7`, `docs f81c9855` |

The merge tree being hash-identical to the head tree is the load-bearing fact:
the exact-head CI that ran on `3b22f6d4` tested byte-for-byte what landed, so
there is no gap between what was verified and what is on `main`. All four CI
jobs were green at that head and both review threads were resolved.

### Re-measured on the merge object, not carried forward

The differential sweep was re-run against `06362807` at three depths, varying
**both** sides of the merge:

| depth | pairs | fail-open | disclosed (F4 contract) |
|---|---|---|---|
| 2 | 625 | **0** | 2 |
| 3 | 15,625 | **0** | 12 |
| 4 | 390,625 | **0** | 42 |
| **total** | **406,875** | **0** | 56 |

The disclosed direction — canonical accepts, graph refuses — is still present
and grows with depth, so the corpus has not gone inert.

**The sweep still bites.** With the fix removed from the merge object, the same
corpus at the same three depths reports **1 / 3 / 54** fail-open, and the F10
suite drops from 7 passed to **4 failed**:

    test_f10_graph_refuses_a_render_canonical_refuses[crossed-a-b]
    test_f10_graph_refuses_a_render_canonical_refuses[reversed-end-before-begin]
    test_f10_a_poisoned_field_cannot_brick_the_projection
    test_f10_no_fail_open_divergence_across_a_differential_sweep

The mutation was applied under a sha256 assertion that it changed the file and
the source restored byte-identical (`1d9c0f84` before and after).

### Gates on the merge object

| gate | result |
|---|---|
| F10 suite | 7 passed |
| freeze guard + lifecycle sweep | 81 passed |
| full suite | 5,733 passed, 8 skipped, 4 xfailed |
| `ruff check .` | clean |
| `mypy src` | clean, 405 source files |

### What this seal does NOT claim

- **Not that upstream reachability is established.** A live corruption path is
  demonstrated at the render and write layers; whether a full
  `discover -> ingest -> graphify` run with attacker-controlled sources can plant
  such a field value is not shown.
- **Not that the two surfaces agree in all directions.** They deliberately do
  not; F4's disclosed contract is intact and asserted.
- **Not that `ingestion.py` is covered.** A third writer, owner-gated behind a
  frozen surface needing an owner-approved sha256-pinned exception under
  `docs/atlas-3/ARCHITECTURE.md` §9.1.

### Corrections this package needed before it could be sealed

Three, all found by verification or by review, all in the **claim record**
rather than the code — which held from the first reproduction:

1. **Blast radius understated.** An earlier revision called the defect defence
   in depth needing a broken renderer. Reproduction proved a durable
   denial-of-refresh: the pre-fix writer *wrote* the poisoned note, after which
   every later refresh, including a clean one with zero relationships, was
   permanently refused.
2. **Corrected in some copies, not all.** That retraction reached the WORKLOG,
   the backlog and this receipt's Blast radius section — but not the test
   module's docstring, nor this receipt's own `What is not claimed` list, whose
   first bullet still asserted the retracted claim in the conclusion a reader
   reaches last. `3b22f6d4` fixed both, explicitly rather than by silent swap.
3. **A count that was wrong by one.** The receipt named four propagating
   relationship fields; there are five. The fifth,
   `provenance.graphify_artifact_refs[].relative_path`, is the one that bypasses
   `_redact_text` entirely.

A fourth, from the code side: the first version of the no-write test bound
`before = NO_HUMAN_PRIOR` and asserted `before == NO_HUMAN_PRIOR` — two names for
one immutable `str`. Both review bots and verification caught it independently.
It was replaced by the end-to-end reproduction, which fails without the fix.
