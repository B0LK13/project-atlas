r"""AS-OBSIDIAN-CAPTURE-001-F8 negative controls, reproducible from a checkout.

Each control simulates marker matching becoming MORE tolerant -- the direction
that fails quietly, since a tolerant matcher does not error, it starts refusing
ordinary human prose. Mechanically it canonicalises the *input document* inside
``merge_protected_regions`` rather than relaxing the matcher itself; the two are
observationally identical on this suite, and verification confirmed that by
running an independently constructed matcher-relaxing family and obtaining the
same six cells. The distinction is recorded because "makes matching more
tolerant" describes the modelled fault, not the edit.

Each is run twice -- against the F3 corpus as it exists on the merge base, and
against the corpus with F8's four split-token pins -- because a
control that only shows the new tests failing proves they are tests, not that
they are needed.

Expected:

    control                                  base corpus (37)     with pins (45)
    A  broadly whitespace-tolerant            1 caught             9 caught
    B  break inside the token only            0 caught, 37 clean   6 caught
    C  whitespace around the colons only      0 caught, 37 clean   2 caught

The "with pins" column counts both the four corpus entries and the four
byte-level assertions F8 adds, which is why it exceeds the number of new corpus
cases. The base-corpus column is the load-bearing one and is unaffected by them.

B and C are load-bearing: both pass entirely undetected against the base corpus.
A is caught by the pre-existing ``extra-inner-spacing`` case alone, which is why
A on its own would be weak evidence that the pins add anything.

Usage:  python docs/scripts/f8_near_miss_controls.py <repo-root> [base-ref]
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

TEST = "tests/unit/test_as_obsidian_capture_001_f3.py"
SRC = "src/project_atlas/protected_regions.py"

ANCHOR = (
    'GENERATED_START = "<!-- atlas:generated:start -->"\n'
    'GENERATED_END = "<!-- atlas:generated:end -->"'
)

CONTROLS: dict[str, str] = {
    "A broadly whitespace-tolerant": r'''import re as _re
_A_S = r"<!--\s*atlas\s*:\s*generated\s*:\s*s\s*t\s*a\s*r\s*t\s*-->"
_A_E = r"<!--\s*atlas\s*:\s*generated\s*:\s*e\s*n\s*d\s*-->"
def _mut(t):
    t = _re.sub(_A_S, GENERATED_START, t, flags=_re.S)
    return _re.sub(_A_E, GENERATED_END, t, flags=_re.S)''',
    "B break inside the token only": r'''import re as _re
def _mut(t):
    t = _re.sub(r"<!-- atlas:generated:s\s*t\s*a\s*r\s*t -->", GENERATED_START, t, flags=_re.S)
    return _re.sub(r"<!-- atlas:generated:e\s*n\s*d -->", GENERATED_END, t, flags=_re.S)''',
    "C whitespace around the colons": r'''import re as _re
def _mut(t):
    t = _re.sub(r"<!-- atlas\s*:\s*generated\s*:\s*start -->", GENERATED_START, t)
    return _re.sub(r"<!-- atlas\s*:\s*generated\s*:\s*end -->", GENERATED_END, t)''',
}


def _run(root: pathlib.Path) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST, "-o", "addopts=", "-q", "--no-header"],
        capture_output=True, text=True, cwd=root,
    )
    tail = [ln for ln in proc.stdout.splitlines() if "passed" in ln or "failed" in ln]
    return tail[-1].strip() if tail else "?"


def main(root: pathlib.Path, base_ref: str) -> int:
    src, test = root / SRC, root / TEST
    # bytes, not text: ``write_text`` translates newlines, so on Windows a
    # restore would rewrite both files with CRLF instead of returning them.
    src_orig, test_pinned = src.read_bytes(), test.read_bytes()
    test_base = subprocess.run(
        ["git", "-C", str(root), "show", f"{base_ref}:{TEST}"],
        capture_output=True, check=True,
    ).stdout

    try:
        for corpus_name, corpus in (("base corpus", test_base), ("with pins", test_pinned)):
            test.write_bytes(corpus)
            print(f"\n--- {corpus_name} ---")
            print(f"    baseline                          {_run(root)}")
            for label, mutation in CONTROLS.items():
                patched = src_orig.replace(
                    ANCHOR.encode(), (ANCHOR + "\n\n" + mutation + "\n").encode()
                )
                assert patched != src_orig, f"MUTATION NO-OP: {label}"
                idx = patched.index(b"def merge_protected_regions(")
                doc = patched.index(b'"""', patched.index(b":\n", idx))
                end = patched.index(b'"""', doc + 3) + 3
                patched = patched[:end] + b"\n    existing = _mut(existing)" + patched[end:]
                before = hashlib.sha256(src_orig).hexdigest()
                src.write_bytes(patched)
                assert hashlib.sha256(src.read_bytes()).hexdigest() != before
                print(f"    {label:33s} {_run(root)}")
                src.write_bytes(src_orig)
    finally:
        src.write_bytes(src_orig)
        test.write_bytes(test_pinned)

    restored = (
        hashlib.sha256(src.read_bytes()).hexdigest()
        == hashlib.sha256(src_orig).hexdigest()
    )
    print(f"\n  sources restored byte-identical: {restored}")
    return 0 if restored else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(pathlib.Path(sys.argv[1]).resolve(),
                          sys.argv[2] if len(sys.argv) > 2 else "origin/main"))
