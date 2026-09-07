# AS-OBSIDIAN-CAPTURE-001-F3 — reserved marker closure

**Owner policy:** Atlas structural marker spellings are **reserved everywhere**,
including inside a HUMAN protected region. HUMAN payload is *not* opaque. Raw
HUMAN bytes are immutable — no auto-escaping, no normalisation, no zero-width
rewriting.

**Status:** implemented, awaiting independent verification. Not sealed.

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
mask the real error. When the HUMAN markers cannot be paired by a simple depth
walk, the containment fact is omitted rather than guessed. A duplicated
generated marker *outside* any HUMAN region is correspondingly **not** reported
as a region collision — pinned by its own test.

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

Byte fidelity on accepted content: LF, **CRLF**, Unicode (`naïve café — ✅ 日本語
🎉`), leading/trailing whitespace, Markdown, HTML-like prose, and content with no
trailing newline all round-trip unchanged. A CRLF note carrying a reserved
marker still fails closed byte-identical.

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
| remove the diagnostic classification | the 4 diagnostic tests fail | 4 failed, exactly those |
| emulate an escaping strategy on preserved HUMAN blocks | byte-preservation tests catch it | 6 failed |

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
| F3 suite | **31 passed** |
| F3 + capture + F1/F2 + F4 + graph projection + Obsidian suites | **243 passed, 0 failed** |
| `ruff check .` | All checks passed |
| `mypy src` | Success, 405 source files |

Broader suite: 4 failures, all in `tests/unit/test_logging.py`. These are **not**
caused by this change — they reproduce identically on unmodified main in this
environment. Cause: those tests run the CLI in a subprocess, which does not
inherit `PYTHONPATH` and so resolves `project_atlas` through the editable
install to the main checkout, which currently sits on a branch predating the
logging fix `5d0ed763`. CI is authoritative here.

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
