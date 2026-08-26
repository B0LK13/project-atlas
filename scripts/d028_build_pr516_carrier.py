#!/usr/bin/env python3
"""Build PR516 integration carrier on integrated main (D-028)."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAIN = "f6b2495a03196901a5a72c2cf3451d4504b54d5f"
PR516 = "0e989fdff9b9e1d4907e194312e3dcc66f507fe0"
POST605 = "5e75e45deb4b84de8b284fde3dfc990ed38f63a6"

GE_PREFIX = "atlas-vault-documentation/skills/atlas-golden-estate-curator/"
EVIDENCE_FILES = [
    "docs/evidence/D-CLOUD-AUG26-GE-WINDOWS-REMEDIATION-020.md",
    "docs/evidence/D-CLOUD-AUG26-GE-WINDOWS-REMEDIATION-020-LOCAL-REBIND.md",
]


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO), *args], text=True, errors="replace"
    ).strip()


def git_show(rev: str, path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO), "show", f"{rev}:{path}"],
        text=True,
        errors="replace",
    )


def main() -> int:
    # GE skill files from PR516
    pr516_files = [
        line
        for line in git("diff", "--name-only", MAIN, PR516).splitlines()
        if line.startswith(GE_PREFIX) or line in EVIDENCE_FILES
    ]
    ci_path = ".github/workflows/ci.yml"
    if ci_path not in git("diff", "--name-only", MAIN, PR516).splitlines():
        print("WARN: ci.yml not in PR516 delta", file=sys.stderr)

    for path in pr516_files:
        content = subprocess.check_output(
            ["git", "-C", str(REPO), "show", f"{PR516}:{path}"]
        )
        dest = REPO / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)

    # CI semantic merge: main + GE test path
    ci = git_show(MAIN, ci_path)
    ci_pr516 = git_show(PR516, ci_path)
    if "atlas-golden-estate-curator/tests" not in ci:
        # take PR516 control-plane pytest line only if additive
        m = re.search(
            r"run: python -m pytest atlas-vault-documentation/tests[^\n]+",
            ci_pr516,
        )
        if m:
            ci = ci.replace(
                "run: python -m pytest atlas-vault-documentation/tests --tb=short -q --no-cov",
                m.group(0),
            )
    (REPO / ci_path).write_text(ci, encoding="utf-8", newline="\n")

    # WORKLOG KEEP_BOTH
    main_wl = git_show(MAIN, "WORKLOG.md")
    pr516_wl = git_show(PR516, "WORKLOG.md")
    sections: list[str] = []
    for m in re.finditer(r"^## (.+)$", pr516_wl, re.M):
        title = m.group(1)
        if any(
            k in title
            for k in ("Golden Estate", "GE ", "D-194", "GE-WIN", "GE Windows")
        ):
            start = m.start()
            nxt = re.search(r"^## ", pr516_wl[m.end() :], re.M)
            end = m.end() + nxt.start() if nxt else len(pr516_wl)
            block = pr516_wl[start:end].strip()
            if block not in main_wl:
                sections.append(block)

    merged = main_wl.rstrip()
    post605_wl = git_show(POST605, "WORKLOG.md")
    m605 = re.search(
        r"## Lane C REPORT READ convergence.*?(?=\n## |\Z)", post605_wl, re.S
    )
    if m605 and "Lane C REPORT READ convergence" not in merged:
        merged += "\n\n---\n\n" + m605.group(0).strip()

    merged += (
        "\n\n---\n\n## D-028 — #516 Golden Estate integration chronology (append-only)\n\n"
        f"Carrier base: integrated main `{MAIN[:8]}`. Policy: KEEP_BOTH_CHRONOLOGICAL.\n\n"
    )
    merged += "\n\n".join(sections) if sections else "(no unique GE sections)\n"
    merged += "\n"
    (REPO / "WORKLOG.md").write_text(merged, encoding="utf-8", newline="\n")

    subprocess.check_call(["git", "-C", str(REPO), "add", "-A"])
    print("staged", len(pr516_files) + 3, "paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
