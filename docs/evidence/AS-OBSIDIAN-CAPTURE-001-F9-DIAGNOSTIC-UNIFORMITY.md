# AS-OBSIDIAN-CAPTURE-001-F9 — one marker diagnosis, whichever writer refuses

**Status:** implemented, awaiting independent verification. **Not sealed.**

## The defect

A generated-marker collision is one operator condition. It did not read as one.
Reproduced on `e264d599` and re-checked on the current base `7f3dff69` with the identical corrupt note put
through both generated-span-preserving writers:

    canonical : malformed-generated-markers:count,begin=2,end=1,expected=1,no-write:n.md
    graph     : malformed-generated-markers:n.md

What an operator was told about their own file therefore depended on an internal
routing detail they cannot observe — which surface happened to reach the note
first. The canonical message names the reason, the observable counts, what was
expected, whether a reserved spelling demonstrably sits inside a HUMAN region,
and — most useful of all — that **nothing was written**. The graph message names
a path.

Recorded in the F1–F4 residual register as "the diagnostic is not uniform across
surfaces", with the five `graph_projections` sites and three `ingestion.py`
sites enumerated. This package closes the five; the three are owner-gated.

## Scope: diagnosis, not policy

Exactly the same notes are refused, with the same fail-closed guarantee and the
same bytes left on disk. This is pinned, not assumed: every corrupt shape is
asserted refused *and* asserted to leave the note byte-identical, and a positive
control asserts a well-formed note still merges.

The message **prefix** is unchanged, so the change is backward compatible with
every existing assertion matching `malformed-generated-markers` — **100 tests across five suites**, verified passing before and after.

## One site gets an honest reason instead of the shared one

The fifth site is not a marker malformation at all. It refuses because the
*fresh render* offers no generated span to substitute — an Atlas-side condition,
not a corrupt note. Reporting it as `malformed-generated-markers` pointed the
operator at the wrong artifact entirely. It now reads
`rendered-has-no-generated-span`, and a test asserts the reason token is not
`count`.

## Negative controls

Five mutations, each applied under a sha256 assertion that it changed the file,
each reverted with both sources confirmed byte-identical afterwards.

| control | reverted | result |
|---|---|---|
| baseline | — | **33 passed** |
| A | count site → bare message | **12 failed** |
| B | end-before-begin site → bare | **4 failed** |
| C | `_generated_span` site → bare | **4 failed** |
| D | rendered-no-span site → bare | **1 failed** |
| E | `_generated_span` reason always `count` | **2 failed** |

**A test that could not fail, found by review.** An earlier revision asserted
the note was left byte-identical by comparing the `existing` *string* against
itself before and after the call. A `str` is immutable, so that assertion could
not fail and pinned nothing -- while this receipt cited it as proof the bytes
were untouched. It now drives the real writer against a real vault and asserts
the file's sha256.

**And then a second one, in the commit that removed the first.** The companion
residue test globbed `*.tmp` -- a suffix this module never writes, since
`_promote` stages as `.<name>.<txn>.atlas-stage` and `.atlas-backup`. Worse, the
control that appeared to validate it renamed staging to `.tmp`, matching the
test's glob rather than the code's naming, so the control validated the
assertion against itself. Verification caught both halves.

It now compares the **whole vault, byte for byte**, before and after a refused
refresh, which holds regardless of naming. And the underlying fact is stronger
than "no residue": the merge raises while the write plan is still being built,
so `_promote` is never reached at all -- measured at **zero invocations** during
a refusal. Residue is structurally impossible, not merely absent. Controlled
with the code's own convention: leaking a uuid-unique `.atlas-stage` file **on the refusing pass only** fails
exactly **1** of 33 -- this test and nothing else. Two ways to get that number
wrong, both encountered: an earlier revision said 5, which a note-clobber alone
fully produces with the residue contributing none of it; and a mutation that
leaks on *every* call also fails 4 unrelated tests, because during setup the
parent directory does not exist yet and the leak breaks the write path itself.
The true figure is the better story: this test is the *only* thing that can
detect residue, which is precisely why it had to exist. The old `*.tmp` glob
detected none of it.

**Controls C and E earned their place by first failing to fail.** On the initial
test set, reverting the `_generated_span` site left the suite at **27 passed** —
the tests were not load-bearing there at all. The reason is structural, not an
oversight in the tests: that guard is **unreachable** through
`_merge_protected_regions`, because `_validate_protected_markers` runs first on
both `existing` and `rendered` and already refuses every shape that would
trigger it. It is defence in depth for direct callers.

Four direct-call tests now pin it, which is the only way it can be pinned, and
the controls bite at 4 and 2. This is recorded because the honest reading of a
passing negative control is *"the control is broken, or the protection is not
where I thought"* — here it was the second.

## Out of scope, owner-gated

`ingestion.py` raises a plain `ValueError` at `:103`, `:107` and `:484`, with a
different spelling again — `malformed generated markers`, spaces not hyphens —
and no diagnosis at all. So a third surface reports a third thing for the same
condition, and it is the surface closest to the product boundary.

`src/project_atlas/ingestion.py` is a certified surface frozen by
`test_atlas3_demo_isolation_001`. The only sanctioned edit path is an
owner-approved exception pinned to an exact sha256 under
`docs/atlas-3/ARCHITECTURE.md` §9.1, which this lane cannot self-grant. The fix
is mechanical — the same public helper this package exports — and what is
missing is the owner decision, not engineering. Carried as a residual.

## What is not claimed

- **Not that refusal behaviour changed.** Same notes refused, same bytes on
  disk. If that had changed, controls A–E would not be the whole story.
- **Not that the three surfaces now agree.** Two do. `ingestion.py` is
  untouched and still reports a third spelling with no diagnosis.
- **Not that `_generated_span`'s guard is reachable in production.** It is
  demonstrably not, through the public path; it is pinned by direct call and
  described as defence in depth, which is what it is.
