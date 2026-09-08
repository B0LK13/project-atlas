"""Find live copies of a claim a seal has retracted.

AS-OBSIDIAN-CAPTURE-001 F6/F7 seals. Three consecutive verification rounds
failed on the same defect -- a correction applied to some copies and not all --
and each time the sweep that certified the fix was one degree of freedom too
weak: an exact-string match, then a whitespace-insensitive match, then a match
defeated by word order ("changed evidence prose only" vs "changed only evidence
prose").

So this does not match phrases. It matches CONCEPTS: two token patterns that
must co-occur inside one sentence-sized window, over whitespace-flattened text.
Wording, word order and line wrapping are therefore irrelevant.

It deliberately OVER-reports. A sentence is flagged LIVE unless a retraction
marker appears near it, and unrelated sentences that merely reuse the vocabulary
are flagged too -- this tool cannot tell them apart semantically. Every hit must
be classified by hand. Do not quote its output as a clean bill of health; that
over-reporting is itself the defect it exists to prevent.

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

WINDOW = 320  # bytes of context searched either side for a retraction marker


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
                context = flat[max(0, match.start() - WINDOW) : match.end() + WINDOW]
                is_live = not RETRACTION.search(context)
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
