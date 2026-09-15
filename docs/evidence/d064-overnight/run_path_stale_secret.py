#!/usr/bin/env python3
"""Run path / stale-cache / secrets red-teams and write combined results JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
COMBINED = HERE / "path-stale-secret-results.json"

# Local imports (same directory)
sys.path.insert(0, str(HERE))
import redteam_path_security as path_mod  # noqa: E402
import redteam_secrets_privacy as secrets_mod  # noqa: E402
import redteam_stale_cache as stale_mod  # noqa: E402


def main() -> int:
    path_result = path_mod.run()
    stale_result = stale_mod.run()
    secrets_result = secrets_mod.run()

    # Persist individual artifacts
    (HERE / "redteam_path_security-results.json").write_text(
        json.dumps(path_result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "redteam_stale_cache-results.json").write_text(
        json.dumps(stale_result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "redteam_secrets_privacy-results.json").write_text(
        json.dumps(secrets_result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    hard_counters: dict[str, Any] = {}
    hard_counters.update(
        {f"path.{k}": v for k, v in path_result.get("hard_counters", {}).items()}
    )
    hard_counters.update(
        {f"stale.{k}": v for k, v in stale_result.get("hard_counters", {}).items()}
    )
    hard_counters.update(
        {f"secrets.{k}": v for k, v in secrets_result.get("hard_counters", {}).items()}
    )

    findings = []
    for section, payload in (
        ("path_security", path_result),
        ("stale_cache", stale_result),
        ("secrets_privacy", secrets_result),
    ):
        for row in payload.get("findings") or []:
            item = dict(row)
            item["section"] = section
            findings.append(item)

    high = [f for f in findings if f.get("severity") == "HIGH"]
    hard_nonzero = {k: v for k, v in hard_counters.items() if v != 0}
    statuses = {
        "path_security": path_result.get("status"),
        "stale_cache": stale_result.get("status"),
        "secrets_privacy": secrets_result.get("status"),
    }
    overall = (
        "PASS"
        if all(s == "PASS" for s in statuses.values()) and not high and not hard_nonzero
        else "FAIL"
    )

    combined: dict[str, Any] = {
        "suite": "d064-overnight-path-stale-secret",
        "frozen_tip": "9c71cc2",
        "status": overall,
        "section_status": statuses,
        "hard_counters": hard_counters,
        "hard_counters_nonzero": hard_nonzero,
        "high_findings": len(high),
        "findings": findings,
        "sections": {
            "path_security": path_result,
            "stale_cache": stale_result,
            "secrets_privacy": secrets_result,
        },
        "pass_rule": "All hard counters must be 0; zero HIGH findings.",
    }
    COMBINED.write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(combined, indent=2, sort_keys=True))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
