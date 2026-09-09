# AS-OBSIDIAN-CAPTURE-001-F16 — human bytes across writes that SUCCEED

**Status:** implemented, awaiting independent verification. **Not sealed.**

## The gap, measured rather than asserted

Every protected-region test in this repository pins a **refusal**. Refusals are
the safe direction. The dangerous case is a write that **succeeds** while
altering bytes the operator owns, because by construction every marker, count
and placement check has already passed on it.

`REFUSAL_SAFETY != SUCCESS_PATH_INTEGRITY`.

Measured on `b87b4a22` by parsing the test tree, not by reading it:

| | |
|---|---|
| assertions touching extracted human regions | **8**, across 2 modules |
| of those, comparing an extraction to a **literal** | **8** |
| comparing an extraction to **another extraction** | **0** |

So the invariant itself — *the human regions that come out are the human regions
that went in* — was asserted nowhere, **as a byte-exact invariant**.

Two qualifications this record owes, both from independent verification:

- The **8** counts assertions touching a region *value*. Two more touch only the
  key set, and of the 8, only 2 compare against a true literal — five compare
  against a `_human(...)` helper call and one against a local. The load-bearing
  half, *0 compare an extraction against another extraction*, reproduces exactly.
- `test_f4_differential_randomized_matches_canonical_core` already runs a
  **500-trial randomized success-path sweep** at base, asserting the two writers
  agree and that each operator payload survives every accepted merge. It checks
  substring containment on well-behaved ASCII, so the byte-exact, whitespace and
  CRLF gap this package fills is real — but "asserted nowhere" was too broad and
  is narrowed here.

**A hypothesis I had to discard first.** I expected the existing assertions to be
blind to whitespace and newline changes, because they use `.strip()`. Measured:
they are not. `.strip()` touches only the region's outer edges, and the extracted
region includes its `BEGIN`/`END` markers, so interior trailing runs and CRLF
survive it. The existing assertions are byte-capable; what was missing is the
invariant, a corpus, and the success path to disk — a narrower and more defensible
claim than the one I filed the issue with.

## What this adds

A corpus of **204 prior/rendered pairs** — bodies carrying tabs, leading and
trailing runs, CRLF, blank lines, a no-break space, a zero-width space, emoji,
non-ASCII, backslashes, marker-shaped text, a 300-character body, and two-region
notes whose render lists the regions in the **opposite order** — swept through
every generated-span-preserving merge reachable without an owner-gated exception.

Measured at `b87b4a22`:

    accepted 366    refused 14    human bytes changed 0

The 14 refusals matter as much as the 366: they are evidence the corpus still
reaches the accept/refuse boundary. A corpus that had drifted to all-accept would
report the same zero while proving less, so `MIN_REFUSED` is asserted.

The success path is then followed **to disk** through all three atomic writers —
merge, write, read back, re-extract — because the operator's bytes are only safe
if they are still intact in the file.

## The zero is falsifiable, in the same test run

This lane has shipped sweeps whose zero was structural. So the falsification is
not described here, it is executed: the same corpus is re-run through writers
deliberately corrupted in the two ways this module exists to catch.

| control | measured |
|---|---|
| baseline | **8 passed** |
| real merge normalises CRLF (the #759 defect) | **1 failed** |
| real merge drops one byte per human body | **1 failed** |
| region comparison neutered | **2 failed** |
| corpus truncated to 3 pairs | **2 failed** |
| the only CRLF body removed | **2 failed** |
| refusal counting removed | **1 failed** |
| an unparseable NAME reintroduced | **1 failed** |
| `capture_io` write path normalises CRLF | **1 failed** |
| a fifth splicing module dropped into `src/` | **1 failed** |
| import detection removed from the derivation | **1 failed** |
| the re-export alias dropped | **1 failed** |
| the detector returns nothing | **2 failed** |
| restored | **8 passed** |

Each mutation applied under an anchor assertion, file restored byte-identical
(`5ed8aea2f7b0`). **Two mutations initially reported "8 passed" because the anchor did
not match** -- shell escaping mangled a `\r\n` literal, and a tuple element had
no leading whitespace. An inert mutation reporting green is the same defect this
module exists to catch, so both were re-applied through a file-based mutator and
only then counted.



**Two of these controls were rewritten because the first versions could not
fail.** I had "removed the disk assertion" and "neutered the exclusion assertion"
— but deleting an assertion can never make a test fail. The honest form is to
break the thing each guard *protects*: corrupt the writer, and actually add the
frozen writer to the sweep. Both then bit immediately.

The last row is worth its own line: adding `ingestion` fails the **invariant**
test as well as the exclusion test, which demonstrates the #759 CRLF defect
through this harness. The exclusion is protecting the suite from a real,
reproduced defect rather than a hypothetical one.

## The full set of writers, derived rather than declared

An earlier revision of this package swept two merge paths and two atomic writers
and called that the writer set. It was not. Derived mechanically from the source
tree -- every module importing or calling `merge_protected_regions`,
`read_note_text` or `_generated_content`, which are the only ways to obtain a
prior note's human content in order to write it back -- there are **four**:

| module | how it is covered |
|---|---|
| `graph_projections.py` | merge swept; disk via `_promote` |
| `obsidian_projection.py` | shares the canonical merge; disk via `_write_atomic` |
| `obsidian_capture_note.py` | shares the canonical merge; **disk via its own `_write_atomic` → `capture_io.write_atomic_under_root`** |
| `ingestion.py` | **excluded** — frozen surface, known CRLF defect (#759) |

The third row is the gap this revision closes. `obsidian_capture_note` does not
reuse either atomic writer above; it has its own, delegating to
`capture_io.write_atomic_under_root`. The previous revision's disk round trip
claimed coverage broader than the code behind it.

**The set is now enforced, not documented.** `test_f16_every_splicing_writer_is_covered_or_explicitly_excluded`
derives the list at test time and fails if a module can splice human regions and
is neither swept nor explicitly excluded with a recorded reason. Adding a fifth
writer therefore cannot pass review silently — measured: dropping a hypothetical
fifth splicing module into `src/` fails that test immediately.

**The derivation keys on the original imported name**, so renaming on import
cannot hide a writer, and on the known local aliases too, so re-exporting through
a third module cannot either. Both are now exercised against synthetic modules
rather than asserted about.

An earlier revision claimed alias-following was pinned by an assertion. It was
not: discovery filters on the *un-aliased* name, so alias resolution was never
load-bearing for it, and that assertion passed just as readily on a derivation
resolving no aliases at all. Verification measured exactly that. The assertion
is replaced by feeding the detector a renamed import and a re-export and
requiring the right verdict.

**What the derivation does NOT close.** Verification demonstrated four evasions.
The re-export is now caught; three remain and are measured:
`importlib.import_module` plus `getattr` with split literals;
`module.__dict__["merge_protected_regions"]`; and a hand-rolled splice using
`Path.read_bytes` and its own regex, which mentions none of these names at all.
That last one falsifies the original premise directly — those three functions are
**not** the only way to reach a prior note's human bytes, and nothing enforces
that they are. The guard makes the *accidental* new writer hard to introduce; it
does not make the set closed, and an earlier revision of this document said it
did.

**The guard caught its author on its first run.** An earlier revision of the
coverage table listed `protected_regions.py`. That module *defines* the merge; it
does not splice into a prior note, so it is the implementation rather than a
writer. The stale-entry half of the assertion fired, which is the guard doing
exactly what it exists to do.

## What is NOT covered, and why

`ingestion._generated_content` is the fourth generated-span-preserving writer.
It is excluded because `src/project_atlas/ingestion.py` sits on the frozen
surface enumerated by `tests/unit/test_atlas3_demo_isolation_001.py`. Including
it would fail this suite for a defect this package does not own, and fixing that
defect needs an owner-approved sha256-pinned exception under
`docs/atlas-3/ARCHITECTURE.md` §9.1 — which this lane cannot self-grant.

`FROZEN_SURFACE != SELF_GRANTED_PERMISSION`.

The exclusion is asserted by a test, so it stays a decision rather than becoming
an accident, and that test names the condition for reversing it.

## What is not claimed

- **Not that the writers are correct in general.** Only that across this corpus,
  no accepted write altered human bytes. The corpus is finite and hand-chosen.
- **Not `HUMAN_CONTENT_INTEGRITY = CONTINUOUSLY_VERIFIED` for Atlas.** Three of
  the four generated-span-preserving writers are now continuously verified on the
  success path; the fourth is the known defect at #759 and remains owner-gated.
  The honest statement is *continuously verified for the writers this lane may
  touch, with the exact blocker identified*.
- **Not that refusal coverage changed.** This adds success-path coverage; the
  existing refusal tests are untouched.
- **Not a policy change.** No `src/` file is modified by this package.
