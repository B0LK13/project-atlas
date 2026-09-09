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
that went in* — was asserted nowhere.

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

    accepted 332    refused 12    human bytes changed 0

The 12 refusals matter as much as the 332: they are evidence the corpus still
reaches the accept/refuse boundary. A corpus that had drifted to all-accept would
report the same zero while proving less, so `MIN_REFUSED` is asserted.

The success path is then followed **to disk** through both atomic writers —
merge, write, read back, re-extract — because the operator's bytes are only safe
if they are still intact in the file.

## The zero is falsifiable, in the same test run

This lane has shipped sweeps whose zero was structural. So the falsification is
not described here, it is executed: the same corpus is re-run through writers
deliberately corrupted in the two ways this module exists to catch.

| control | measured |
|---|---|
| baseline | **6 passed** |
| real writer normalises CRLF (the #759 defect) | **1 failed** — the invariant test |
| real writer drops one byte per human body | **1 failed** — the invariant test |
| corpus truncated to 3 pairs | **2 failed** |
| region comparison neutered (`if False`) | **2 failed** |
| `changed` list silently cleared | **2 failed** |
| the only CRLF body removed from the corpus | **2 failed** |
| refusal counting removed | **1 failed** |
| **`_write_atomic` corrupted to normalise CRLF on the way to disk** | **1 failed** — the round-trip test |
| **`ingestion._generated_content` added to the sweep** | **2 failed** — invariant *and* exclusion |
| restored | **6 passed** |

Each mutation was applied under an anchor assertion and the file restored
byte-identical (`56357fc0`).

**Two of these controls were rewritten because the first versions could not
fail.** I had "removed the disk assertion" and "neutered the exclusion assertion"
— but deleting an assertion can never make a test fail. The honest form is to
break the thing each guard *protects*: corrupt the writer, and actually add the
frozen writer to the sweep. Both then bit immediately.

The last row is worth its own line: adding `ingestion` fails the **invariant**
test as well as the exclusion test, which demonstrates the #759 CRLF defect
through this harness. The exclusion is protecting the suite from a real,
reproduced defect rather than a hypothetical one.

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
