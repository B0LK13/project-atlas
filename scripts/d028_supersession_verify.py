#!/usr/bin/env python3
"""Verify D-027 supersession still holds against live main."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAIN = "f6b2495a03196901a5a72c2cf3451d4504b54d5f"
PACKET = REPO / "docs/evidence/D-027-SUPERSESSION-PACKET.json"


def ancestor(main: str, head: str) -> bool:
    r = subprocess.run(
        ["git", "-C", str(REPO), "merge-base", "--is-ancestor", head, main],
        capture_output=True,
    )
    return r.returncode == 0


def main() -> int:
    data = json.loads(PACKET.read_text(encoding="utf-8"))
    drift = []
    for pr in data["embedded_open_prs"]:
        num = pr["PR_NUMBER"]
        head = pr["HEAD"]
        if not ancestor(MAIN, head):
            drift.append({"pr": num, "head": head, "reason": "not_ancestor_of_main"})
    out = {
        "main_head": MAIN,
        "checked": len(data["embedded_open_prs"]),
        "drift": drift,
        "unique_delta_expected": 0,
        "verdict": "PASS" if not drift else "FAIL",
    }
    out_path = REPO / "docs/evidence/D-028-SUPERSESSION-VERIFY.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
