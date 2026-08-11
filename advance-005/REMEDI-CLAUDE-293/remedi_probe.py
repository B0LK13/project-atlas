"""ADVANCE-005 REMEDI-CLAUDE-293 post-fix probes (003/004/010)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from project_atlas.eval_substrate import (  # noqa: E402
    EVAL_HOLDOUT_EXPECTED_PATH_ENV,
    EVAL_SCORING_CAPABILITY_ENV,
    build_eval_score_receipt,
    holdout_root,
    load_cases,
)

OUT = Path(__file__).resolve().parent / "remedi-probe.txt"
VAULT = Path(__file__).resolve().parent / "_probe_vault"
SECRETS = REPO / "tests" / "fixtures" / "eval_holdout_expected.json"


def main() -> int:
    lines: list[str] = []
    hold_file = holdout_root(REPO) / "cases" / "EV-HOLD-001-exact.json"

    lines.append("=== IDENTITY ===")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip()
    lines.append(f"REPO={REPO}")
    lines.append(f"HEAD_SHA={head}")

    lines.append("")
    lines.append("=== 010: git-tracked holdout bodies ===")
    payload = json.loads(hold_file.read_text(encoding="utf-8"))
    tracked = subprocess.check_output(
        ["git", "ls-files", "fixtures/eval/holdouts/hidden"],
        cwd=REPO,
        text=True,
    ).strip()
    lines.append(f"git_tracked_holdouts={tracked.replace(chr(10), ';')}")
    lines.append(f"holdout_case_has_expected_field={'expected' in payload}")
    lines.append(f"holdout_plaintext_expected={payload.get('expected', '[absent]')}")

    lines.append("")
    lines.append("=== 004: role-not-trust ===")
    public_only = load_cases(REPO, "scoring")
    lines.append(
        "load_cases_scoring_without_cap="
        + str(sorted(c["case_id"] for c in public_only))
    )
    os.environ[EVAL_SCORING_CAPABILITY_ENV] = "1"
    os.environ[EVAL_HOLDOUT_EXPECTED_PATH_ENV] = str(SECRETS)
    armed = load_cases(REPO, "scoring")
    lines.append(
        "load_cases_scoring_with_cap="
        + str(sorted(c["case_id"] for c in armed))
    )
    lines.append(
        "holdout_expected_loaded="
        + str(next(c["expected"] for c in armed if c["case_id"] == "EV-HOLD-001"))
    )

    lines.append("")
    lines.append("=== 003: receipt redaction ===")
    VAULT.mkdir(parents=True, exist_ok=True)
    receipt = build_eval_score_receipt(
        VAULT,
        record_id="remedi-hold",
        repo_root=REPO,
        predictions={
            "EV-PUB-001": "validate-ok",
            "EV-PUB-002": "discover-x",
            "EV-HOLD-001": "conflict-detected",
            "EV-HOLD-002": "lineage-stable",
        },
        include_holdouts=True,
    )
    hold_rows = [r for r in receipt["results"] if r["visibility"] == "holdout"]
    lines.append(f"holdout_rows_expected_norm={[r['expected_norm'] for r in hold_rows]}")
    lines.append(
        "holdout_rows_expected_redacted="
        + str([r.get("expected_redacted") for r in hold_rows])
    )
    artifact = json.dumps(receipt)
    lines.append(
        "ARTIFACT_CONTAINS_holdout_expected_norm="
        + str(any(r["expected_norm"] for r in hold_rows))
    )
    lines.append(
        "ARTIFACT_CONTAINS_conflict-detected_in_expected_norm="
        + str(any(r["expected_norm"] == "conflict-detected" for r in hold_rows))
    )

    lines.append("")
    lines.append("=== BOUNDARY SUMMARY ===")
    lines.append(
        "PLAINTEXT_EXPECTED_IN_HOLDOUT_FILES="
        + ("NO" if "expected" not in payload else "YES")
    )
    lines.append(
        "PLAINTEXT_EXPECTED_IN_GENERATED_RECEIPT="
        + (
            "NO"
            if not any(r["expected_norm"] for r in hold_rows)
            else "YES"
        )
    )
    lines.append("SCORING_CAPABILITY_GATE=YES")
    lines.append("HIDDEN_HOLDOUT_ISOLATION=PARTIAL_TOWARD_PASS")
    lines.append("EVALUATOR_READY_FOR_AUTOLAB=NO")
    lines.append("ATLAS_OPT_WAKE_GATE=CLOSED")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
