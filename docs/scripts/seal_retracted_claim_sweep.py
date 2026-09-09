r"""Find live copies of a claim a seal has retracted.

AS-OBSIDIAN-CAPTURE-001 F6/F7 seals. Three consecutive verification rounds
failed on the same defect -- a correction applied to some copies and not all --
and each time the sweep that certified the fix was one degree of freedom too
weak: an exact-string match, then a whitespace-insensitive match, then a match
defeated by word order ("changed evidence prose only" vs "changed only evidence
prose").

So this does not match phrases exactly. It matches two token patterns that must
co-occur inside one sentence-sized window, over whitespace-flattened text.
**Word order and line wrapping are therefore irrelevant. Wording is not** -- see
the limits below.

What it does NOT do, stated plainly, because overstating a verification method
is the defect this file exists to prevent:

* **It matches a fixed vocabulary, not meaning.** The anchors are literal
  bigrams (``claim record``, ``evidence prose``). A one-word substitution walks
  straight past it -- "changed only *documentation* prose", or "lived in the
  *record of claims* rather than the *implementation*". Independent verification
  refuted the opposite claim with two one-word rewrites. An earlier revision of
  THIS docstring asserted wording was irrelevant and then contradicted itself
  nine lines later, because the correction was appended beneath the false
  sentence instead of replacing it -- the same defect this file exists to catch,
  committed inside it.
* **Sentence windows are naive.** A ``.`` inside a filename ends a window early,
  so a claim split across ``…\`WORKLOG.md\`. Evidence prose was all that moved``
  is missed.
* **It over-reports.** Unrelated sentences reusing the vocabulary are flagged;
  they cannot be told apart semantically. Every hit needs a human.

The retraction test is deliberately scoped to the SENTENCE, not a byte window
around it. An earlier version searched 320 bytes either side, which silently
downgraded a verbatim restatement of a retracted claim to ``retraction`` merely
because it sat next to the paragraph retracting it -- precisely where such a
restatement would naturally be written, and an UNDER-reporting hazard the
docstring did not disclose. Verification demonstrated that defeat; it is closed
here rather than merely documented.

The consequence of that scoping, disclosed rather than left implicit: a
retraction marker inside the SAME sentence still suppresses. A sentence that
both invokes a retraction and asserts the retracted claim is bucketed as a
retraction. That text is visibly self-contradictory and cannot arise from this
lane's actual failure mode -- a stale copy left behind elsewhere carries no
marker, which is why every real stale copy found in verification was a plain
assertion -- so it is an accepted limit, not a closed one.

Do not quote this tool's output as a clean bill of health.

Usage:  python docs/scripts/seal_retracted_claim_sweep.py FILE [FILE ...]
Exit:   0 if nothing is flagged LIVE, 1 otherwise (review each hit regardless).
"""

from __future__ import annotations

import pathlib
import re
import sys

#: Each retracted claim, as two patterns that must co-occur in one window.
CLAIMS: dict[str, tuple[re.Pattern[bytes], re.Pattern[bytes]]] = {
    "A: all post-round-1 findings were claim-record, not code": (
        re.compile(rb"claim record", re.I),
        re.compile(rb"(not the code|rather than the code|rather than in the code)", re.I),
    ),
    "B: all post-round-1 rounds changed only evidence prose": (
        re.compile(rb"evidence prose", re.I),
        re.compile(rb"(only|prose only)", re.I),
    ),
}

RETRACTION = re.compile(
    rb"(earlier revision|\*\*false\*\*|overstates|retract|the seals said)", re.I
)


def sweep(paths: list[str]) -> int:
    live = 0
    for label, (first, second) in CLAIMS.items():
        print(f"\n=== claim {label} ===")
        hits = 0
        for path in paths:
            flat = re.sub(rb"\s+", b" ", pathlib.Path(path).read_bytes())
            for match in re.finditer(rb"[^.!?]{0,400}[.!?]", flat):
                sentence = match.group(0)
                if not (first.search(sentence) and second.search(sentence)):
                    continue
                hits += 1
                # Scoped to the sentence itself: a retraction marker merely
                # NEARBY must not excuse a live restatement (see module docstring).
                is_live = not RETRACTION.search(sentence)
                live += is_live
                tag = "LIVE" if is_live else "retraction"
                text = sentence.strip().decode("utf-8", "replace")[:150]
                print(f"  [{tag}] {pathlib.Path(path).name}: {text}")
        if not hits:
            print("  (no occurrences)")
    print(f"\n  flagged LIVE: {live}  -- classify every one by hand")
    return 1 if live else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(sweep(sys.argv[1:]))
