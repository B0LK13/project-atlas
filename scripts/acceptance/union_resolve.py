"""Union-resolve live conflict blocks in this repository's append-only files.

`WORKLOG.md` needs care for two reasons discovered while assembling the
integration candidate:

1. It already contains, ON MAIN, committed text that LOOKS like conflict
   markers (`||||||| parent of ...`, `||||||| Stash base`, roughly lines
   5855-6265) -- historical stash/merge residue that is real file content.
   A pass that strips every marker-shaped line corrupts the file.
2. It contains one NUL byte, so it must be read and written with
   `surrogateescape` rather than as clean UTF-8 text.

So this only rewrites complete, live `<<<<<<< / ======= / >>>>>>>` triples
and keeps BOTH sides, which is the correct resolution for an append-only
log where two branches each appended their own entries.
"""
from __future__ import annotations

import sys
from pathlib import Path


def resolve(path: Path) -> int:
    raw = path.read_bytes().decode("utf-8", errors="surrogateescape")
    lines = raw.split("\n")
    resolved = 0
    while True:
        start = next((i for i, ln in enumerate(lines) if ln.startswith("<<<<<<< ")), None)
        if start is None:
            break
        mid = next(
            (i for i in range(start + 1, len(lines)) if lines[i].rstrip() == "======="),
            None,
        )
        end = next(
            (i for i in range((mid or start) + 1, len(lines)) if lines[i].startswith(">>>>>>> ")),
            None,
        )
        if mid is None or end is None:
            break
        lines = lines[:start] + lines[start + 1 : mid] + lines[mid + 1 : end] + lines[end + 1 :]
        resolved += 1
    path.write_bytes("\n".join(lines).encode("utf-8", errors="surrogateescape"))
    return resolved


def main(argv: list[str]) -> int:
    for name in argv:
        p = Path(name)
        print(f"{p}: union-resolved {resolve(p)} live block(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
