#!/usr/bin/env python3
"""D-029 REPORT READ + node audit with merge-base semantics."""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAIN = "f6b2495a03196901a5a72c2cf3451d4504b54d5f"


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def pr_unique_paths(head: str) -> list[str]:
    mb = git("merge-base", MAIN, head)
    return [p for p in git("diff", "--name-only", mb, head).splitlines() if p]


def rr_disposition(head: str) -> str:
    unique = pr_unique_paths(head)
    prod = [p for p in unique if p.startswith("src/")]
    read_files = [
        p for p in prod
        if "web_api" in p and ("read" in p or "index_status" in p or "status" in p)
    ]
    if not prod:
        return "SUPERSEDED"
    if read_files and all(
        subprocess.run(
            ["git", "-C", str(REPO), "cat-file", "-e", f"{MAIN}:{f}"],
            capture_output=True,
        ).returncode == 0
        for f in read_files
    ):
        return "SUPERSEDED"
    return "BACKLOG_OPTIONAL"


def main() -> None:
    prs = json.loads(
        subprocess.check_output(
            ["gh", "pr", "list", "--state", "open", "--limit", "100", "--json",
             "number,title,headRefOid"],
            cwd=REPO, text=True,
        )
    )
    rr = [p for p in prs if "REPORT READ" in p["title"] or "read lens" in p["title"]]
    inv = []
    for p in rr:
        head = p["headRefOid"]
        disp = rr_disposition(head)
        inv.append({
            "PR_NUMBER": p["number"],
            "HEAD": head,
            "DISPOSITION": disp,
            "UNIQUE_PATHS": pr_unique_paths(head)[:10],
        })
    by_disp = defaultdict(int)
    for i in inv:
        by_disp[i["DISPOSITION"]] += 1
    out = REPO / "docs/evidence/D-029-REPORT-READ-AUDIT.json"
    out.write_text(json.dumps({"audited": len(inv), "by_disposition": dict(by_disp), "inventory": inv}, indent=2), encoding="utf-8")
    print(dict(by_disp))


if __name__ == "__main__":
    main()
