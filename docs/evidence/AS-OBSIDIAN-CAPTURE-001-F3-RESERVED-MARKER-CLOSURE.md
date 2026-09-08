# AS-OBSIDIAN-CAPTURE-001-F3 — reserved marker closure

**Owner policy:** Atlas structural marker spellings are **reserved everywhere**,
including inside a HUMAN protected region. HUMAN payload is *not* opaque. Raw
HUMAN bytes are immutable — no auto-escaping, no normalisation, no zero-width
rewriting.

**Status:** **SEALED 2026-09-08 on main** — merged as PR #717 (merge commit
`48a51875` onto main `15c9a6d6`; candidate head `c6b0ecb8` carried only
docs/evidence corrections over the independently verified behavioural
predecessor `8d19932c`, src/tests byte-identical). Postmerge seal on actual
main: F3 suite + F1/F2 + F4 regression = 246 passed; full suite 5,616 passed /
8 skipped. The pre-merge "awaiting independent verification" status below is
historical record.

## Base and candidate

| field | value |
|---|---|
| `F3_BASE_HEAD` | `15c9a6d6ade3e799178c614cac760ea69951e601` (post-F4 main) |
| `F3_BASE_TREE` | `ca2095785e6e10cb2256b58333de00439c490a00` |

## What was already true, and what actually changed

The safety behaviour this work package exists to guarantee **already held on
main before any change here**, and that was established empirically rather than
assumed. Every reserved spelling placed inside a HUMAN region was already
refused with the note left byte-identical, and every near miss was already
preserved as ordinary prose.

So no parser change was manufactured. Under the minimal-change principle, the
runtime delta is confined to the **diagnostic**: the refusal now reports what
can be observed, where before it said only `malformed-generated-markers:<path>`.

Before:

```
malformed-generated-markers:notes/demo.md
```

After:

```
malformed-generated-markers:count,begin=2,end=1,expected=1,reserved-marker-in-human-region,no-write:notes/demo.md
```

The leading class token is unchanged, so every existing matcher — including the
`GraphProjectionError` translations in `graph_projections.py` — keeps working.

## Causal honesty

The diagnostic states **observable facts only** and makes no authorship claim.
The same failure shape can arise from an operator writing a reserved spelling as
prose, from Atlas corrupting its own generated structure, or from an unrelated
malformed state, and the implementation cannot distinguish those. It therefore
reports counts, the failure reason, and — only when the containment is
structurally determinable — that a reserved spelling sits inside a HUMAN region.

`_outermost_human_spans` is deliberately non-raising: it runs only to enrich a
diagnostic for a document already known to be malformed, so it must not fail and
mask the real error. When the HUMAN markers cannot be paired, the containment
fact is omitted rather than guessed. A duplicated generated marker *outside* any
HUMAN region is correspondingly **not** reported as a region collision — pinned
by its own test.

### The containment check must share the canonical grammar

The first version of this helper matched marker names with `[^\s>]*` and paired
by a bare depth counter. Review caught that, and it was a real false-positive
source: the canonical `_HUMAN_BEGIN` requires `[^\s>]+`, so `<!-- BEGIN HUMAN: -->`
is **not** a region to the canonical parser — yet the permissive helper saw one
and reported `reserved-marker-in-human-region` for a region that does not exist.
A depth counter likewise treated crossed markers as a balanced span, where the
canonical parser refuses them as unpaired.

That is precisely the failure this project keeps meeting: a second parser
drifting from the canonical one. The helper now uses the same `[^\s>]+` grammar
and the same strict name-matched pairing, and returns "not determinable" for an
orphan `END`, a crossed pair, or an unclosed `BEGIN`. Four tests pin the false
positives and a fifth pins that the true positive still reports. A negative
control confirms it: restoring `[^\s>]*` fails the unnamed-marker test.

`no-write` is included because the most useful thing an operator can be told
about a fail-closed refusal is that the note on disk was not touched.

## Accepted / refused matrix

Refused, note byte-identical (5):

| case | outcome |
|---|---|
| exact `atlas:generated:start` inside HUMAN | REFUSE `malformed-generated-markers` |
| exact `atlas:generated:end` inside HUMAN | REFUSE `malformed-generated-markers` |
| **balanced forged pair** (both spellings inside HUMAN) | REFUSE `malformed-generated-markers` |
| exact `BEGIN HUMAN:` marker inside HUMAN | REFUSE `malformed-protected-markers` |
| exact `END HUMAN:` marker inside HUMAN | REFUSE `malformed-protected-markers` |

The balanced forged pair is the load-bearing one. Counting alone would see the
begins and ends match and could call that balanced; it is refused because Atlas
owns exactly **one** generated span, so `start_count > 1` stops a forged pair
becoming valid structure by accident.

Accepted as ordinary prose, bytes preserved (7): bare token without a comment,
extra inner spacing, `startx` suffix variant, uppercase variant, partial token,
ordinary HTML comment, HUMAN marker with no name. Only the exact spelling is
reserved.

Byte fidelity on accepted content: LF, Unicode (`naïve café — ✅ 日本語 🎉`),
leading/trailing whitespace, Markdown, HTML-like prose, and content with no
trailing newline all round-trip unchanged. A CRLF note carrying a reserved
marker still fails closed byte-identical.

**CRLF, scoped precisely.** At the `protected_regions` module level a HUMAN
block containing `\r\n` is preserved verbatim. **End to end through the writers
it is not**, and this receipt previously overstated that. **Four** writers read
the prior note this way -- the three `merge_protected_regions` callers
(`obsidian_capture_note.py:378`, `obsidian_projection.py:360`,
`graph_projections.py:644`) plus `ingestion.py:99` (`_generated_content`), which
preserves a generated span without going through `protected_regions` at all, so
a grep for the merge function misses it. An earlier revision of this receipt
said three. Each uses `Path.read_text(encoding="utf-8")`, whose universal-newline
translation converts `\r\n` to `\n` *before the merge ever sees the bytes*, so a
CRLF HUMAN block returns to disk LF-only. That behaviour is **pre-existing and
reproduces byte-for-byte on base main `15c9a6d6`** — it is not introduced or
changed here — but it does mean the owner policy phrase "no normalisation" is
not currently honoured for line endings at the product boundary. It deserves its
own work package; F3 does not fix it and does not claim to.

Repeat behaviour: a near-miss note is stable across refreshes; a reserved-marker
collision yields the same refusal class twice with no accumulated mutation.

## Byte-preservation proof

The refusal tests assert on encoded bytes, and additionally assert the author's
exact text is still present, that no `U+200B` was inserted, and that no `&lt;!--`
escaping occurred.

## Negative controls

Both were run in scratch and reverted; neither is committed.

| control | expectation | observed |
|---|---|---|
| remove the diagnostic classification | the diagnostic tests fail | **7 failed** at this head (it was 4 at the first candidate `56b1b0c2`; three further tests fail here because two more containment tests and the linearity test were added after that candidate. An earlier revision said 4 was the count "before the containment tests were added" -- that is false: one containment test already existed at `56b1b0c2` and is one of its four failures) |
| emulate an escaping strategy on preserved HUMAN blocks | byte-preservation tests catch it | 6 failed |
| restore the permissive `[^\s>]*` containment grammar | the unnamed-marker false-positive test fails | 1 failed, exactly that one |
| restore the pairwise (quadratic) containment scan | the linearity test fails | 1 failed, at 18.3s -- **timing NOT re-run at the exact head or at any seal; treat as unverified.** The linearity test itself is green |

So the diagnostic tests are load-bearing on the change, and the byte tests would
catch a future regression to auto-escaping.

## Regression status

- **F2 / RegionPath:** PASS. Nested distinct names, `a/x` vs `b/x`, orphan
  behaviour, same-scope duplicate refusal, self-nesting refusal, crossed and
  unclosed markers all unchanged.
- **F4 / graph projections:** PASS. The committed differential harness at 4,000
  trials, seed 20260907, still shows graph converging on canonical exactly —
  2178/1822 accepted/refused with **0** loss, substitution, duplication and
  structural growth on both columns.

## Test counts

| gate | result |
|---|---|
| F3 suite | **37 passed** |
| F3 + capture + F1/F2 + F4 + graph projection + Obsidian suites | **249 passed, 0 failed** -- **not reproducible as stated**: the file set is unspecified, nearest reconstruction 237/0 (also file-set-unspecified). Subsumed by the green full suite |
| `ruff check .` | All checks passed |
| `mypy src` | Success, 405 source files |

Broader suite: **5,616 passed, 8 skipped, 0 failed** under independent
verification, and CI is green on all four required jobs.

An earlier revision of this receipt reported 4 `tests/unit/test_logging.py`
failures as a local environment artifact. Those did **not** reproduce for the
independent verifier, who saw that file pass 18/18. The explanation still stands
as a property of this machine rather than of the change — those tests run the
CLI in a subprocess, which does not inherit `PYTHONPATH` and resolves
`project_atlas` through the editable install to a checkout predating the logging
fix `5d0ed763` — but the claim was more pessimistic than reality and is recorded
here as machine-local, not as a property of this candidate.

### The refusal path must not be slow

Review also caught that the containment check compared every marker occurrence
against every span. That is quadratic on exactly the input which reaches it — a
large malformed note with many markers and many sibling regions — so a refusal
could spend seconds merely formatting its own error. Measured before the fix:
0.01s at 500 regions, 0.17s at 2,000, **1.09s at 5,000**.

Both sequences are ascending and the spans do not overlap, so they are now
walked together. Measured after: **0.012s at 5,000** and 0.070s at 20,000 — from
quadratic to linear, ~90× faster at 5,000. A regression test pins it with a
generous 5s bound at 20,000 regions; the negative control (restoring the
pairwise scan) takes **18.3s** and fails it. That timing was measured at the pre-remediation candidate and has **not** been re-run at the exact head or at any seal; treat the number as unverified.

## Failure atomicity

Driven through the real `graph_projections.write_projection_outputs`, which
writes two projection files in one operation: with legitimate human content in
`relationships.md` and a reserved-marker collision in `graph-health.md`, the
refusal leaves **every file byte-identical**, the first file not rewritten, the
human text intact, and no staging residue. No first-file write followed by a
second-file refusal.

## Known residuals

Recorded rather than left for a reader to discover.

- **Self-nesting containment.** `_outermost_human_spans` pairs
  `BEGIN x … BEGIN x … END x … END x` by name, where the canonical
  `_human_region_spans` refuses it as `ambiguous-protected-region-nesting`
  (reported as 52 of 66,430 exhaustive marker sequences by an independent verifier whose harness was **never committed** -- that figure is **not reconstructible and must not be cited**; the divergence itself is separately confirmed). The
  asserted fact remains true under every reading of that ambiguity — the marker
  really is inside a HUMAN block — but it is the one place the containment check
  speaks about structure the canonical grammar declines to parse.
- **The diagnostic is not uniform across surfaces.** The retained no-HUMAN-regions
  branch in `graph_projections` still emits the bare
  `malformed-generated-markers:<path>`, so an operator can still meet an
  uninformative refusal on that path. Nothing here claims uniformity.

## Claim boundary

Claimed: the exact Atlas marker spellings are reserved syntax wherever they
occur; a collision fails closed; no note bytes change on refusal; near misses
remain ordinary text per the current grammar; the diagnostic now reports
observable structural facts.

**Not claimed:** that arbitrary HTML comments are unsafe; that HUMAN content is
opaque; that any render output is reversible; that a malformed state identifies
operator action; or that Obsidian note corruption in general is solved.

This is implementation evidence, not certification. Independent exact-head
verification and CI are required before merge, and merge authority does not
belong to this lane.
