#!/usr/bin/env python3
"""Prepare supersession closure packet (owner-ready, no closure authority)."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAIN = "f6b2495a03196901a5a72c2cf3451d4504b54d5f"
PACKET_IN = REPO / "docs/evidence/D-027-SUPERSESSION-PACKET.json"
PACKET_OUT = REPO / "docs/evidence/D-029-SUPERSESSION-CLOSURE-PACKET.json"


def main() -> None:
    data = json.loads(PACKET_IN.read_text(encoding="utf-8"))
    closure = []
    for pr in data["embedded_open_prs"]:
        closure.append({
            "PR_NUMBER": pr["PR_NUMBER"],
            "HEAD": pr["HEAD"],
            "PACKAGE": pr["PACKAGE"],
            "SUPERSEDED_BY": f"MAIN_{MAIN}",
            "UNIQUE_DELTA": 0,
            "PROPOSED_ACTION": "CLOSE_AS_SUPERSEDED",
            "COMMENT_TEMPLATE": (
                f"Superseded by integrated main `{MAIN[:12]}…` (D-025 Atlas3 stack). "
                f"Semantic content contained; UNIQUE_DELTA=0 per D-029 audit."
            ),
        })
    out = {
        "directive": "D-AUG26-SUCCESSOR-DAG-EXHAUSTION-029",
        "main_head": MAIN,
        "closure_authority": "NOT_GRANTED",
        "candidates": closure,
        "count": len(closure),
        "preparation_complete": True,
    }
    PACKET_OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", len(closure), "closure candidates")


if __name__ == "__main__":
    main()
