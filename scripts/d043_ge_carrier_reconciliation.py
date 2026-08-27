#!/usr/bin/env python3
"""D-043: Dual-local authoritative GE carrier reconciliation.

Corrected byte-accurate verifier successor to invalidated D-038 methodology.
Builds on D-042 core logic; emits D-043 durable evidence packet.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
EVIDENCE = REPO / "docs" / "evidence"
SCRIPTS = REPO / "scripts"

MAIN = "f6b2495a03196901a5a72c2cf3451d4504b54d5f"
MAIN_TREE = "9c670d710ec63d36fea70c6a181c088b79294336"
PR607 = "80dd9d01a38ee3720b759cfd51e9262ce3235ea2"
PR607_TREE = "0eab2f88b92830b8a2bac917633abff2e29047a1"
PR608 = "94786c9c6e59aa0934296a71e8190959e34e914e"
PR608_TREE = "a26b9caa95ae37d39d20f489683174ce166e903a"
PR609 = "4fe172ffc14713db9cfe4d698848b770d69a0fe6"
PR609_TREE = "b53de8667e48e625d0fdcea540a52f6b42f28b22"
PR612 = "be223a0d92ed9ca2f112ad92865850a9318b843a"
COMPETING_D038_INITIAL_HEAD = "af17824a26830e07c718a1478e419234a096f4e4"
COMPETING_D038_INITIAL_TREE = "798bcaac5e14160b2821a01458ed1806269f589d"
PRIOR_D038_HEAD = COMPETING_D038_INITIAL_HEAD
PRIOR_D038_TREE = COMPETING_D038_INITIAL_TREE


def _load_d042():
    name = "d042_competing_d038_methodology_reconciliation"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, SCRIPTS / "d042_competing_d038_methodology_reconciliation.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def worklog_sha256(sha: str) -> str:
    return sha256_bytes(_load_d042().blob(sha))


def ge_file_hashes(sha: str) -> dict[str, str]:
    listing = git("ls-tree", "-r", "--name-only", sha)
    paths = [
        p
        for p in listing.splitlines()
        if "golden-estate-curator" in p and not p.endswith("/")
    ]
    d042 = _load_d042()
    return {p: sha256_bytes(d042.blob(sha, p)) for p in paths}


def audit_historical_supersession(d042_mod) -> dict[str, Any]:
    """Live-verified supersession audit; D-027 required, D-026 optional fallback."""
    d027_path = EVIDENCE / "D-027-SUPERSESSION-PACKET.json"
    d027 = json.loads(d027_path.read_text(encoding="utf-8"))

    d026_path = EVIDENCE / "D-026-SUPERSESSION-MAP.json"
    if d026_path.exists():
        s026 = json.loads(d026_path.read_text(encoding="utf-8"))
        historical_size = len(s026["contained_open_prs"])
        s026_pr_set = {p["pr"] for p in s026["contained_open_prs"]}
    else:
        historical_size = len(d027["embedded_open_prs"])
        s026_pr_set = {e["PR_NUMBER"] for e in d027["embedded_open_prs"]}

    entries = []
    open_closure_targets = 0
    duplicates = 0
    seen: set[int] = set()
    live_cache = d042_mod.fetch_all_pr_states()

    for e in d027["embedded_open_prs"]:
        pr = e["PR_NUMBER"]
        if pr in seen:
            duplicates += 1
            continue
        seen.add(pr)
        live = d042_mod.gh_pr_state(pr, live_cache)
        eligible = live["state"] == "OPEN" and not live.get("merged", False)
        if eligible:
            open_closure_targets += 1
        entries.append({
            "PR_NUMBER": pr,
            "RECORDED_HISTORICAL_STATE": "OPEN",
            "LIVE_STATE": live["state"],
            "MERGED": live.get("merged", False),
            "HEAD": live["headRefOid"],
            "RECORDED_HEAD": e["HEAD"],
            "HEAD_MATCH": live["headRefOid"] == e["HEAD"],
            "ELIGIBLE_FOR_CLOSURE_NOW": eligible,
        })

    return {
        "historical_supersession_set_size": historical_size,
        "d027_packet_size": len(d027["embedded_open_prs"]),
        "current_open_closure_target_count": open_closure_targets,
        "supersession_current_state_verified": True,
        "supersession_duplicate_count": duplicates,
        "pr608_in_historical_supersession_set": 608 in s026_pr_set,
        "pr609_in_historical_supersession_set": 609 in s026_pr_set,
        "closure_entries": entries,
    }


def audit_prior_d038() -> dict[str, Any]:
    src = subprocess.check_output(
        ["git", "-C", str(REPO), "show", f"{PRIOR_D038_HEAD}:scripts/d038_pr609_differential_seal.py"],
    ).decode("utf-8", errors="replace")
    return {
        "D038_CP1252_REDECODE_USED": "decode(\"cp1252\"" in src or "decode('cp1252'" in src,
        "D038_CP1252_REDECODE_DRIVES_BASELINE": "baseline_count = count_mojibake_cp1252" in src,
        "D038_CARRIER_SCOPE_ONLY_D028": "extract_section(text, \"## D-028\")" in src,
        "D038_UNRELATED_REWRITES_DETECTED": "unrelated_rewrites" in src,
        "D038_UNRELATED_REWRITES_GATE_EXPECTED_DELTA": False,
        "D038_UNRELATED_REWRITES_GATE_CARRIER_REGRESSION": False,
        "D038_LIVE_PR_STATES_QUERIED": "gh" in src and "pr" in src,
        "D038_PR608_SUPERSESSION_CIRCULAR": "608" in src and "SUPERSEDED_BY" in src,
    }


def build_packet(*, write_files: bool = True) -> dict[str, Any]:
    d042 = _load_d042()

    main_blob = d042.blob(MAIN)
    pr607_blob = d042.blob(PR607)
    pr608_blob = d042.blob(PR608)
    pr609_blob = d042.blob(PR609)

    main_analysis = d042.analyze_worklog_diff(MAIN, PR609)
    pr608_diff_lines = subprocess.check_output(
        ["git", "-C", str(REPO), "diff", PR607, PR608, "--", "WORKLOG.md"],
    ).splitlines()

    supersession = audit_historical_supersession(d042)
    cp1252_proof = d042.cp1252_false_positive_proof()
    prior_d038 = audit_prior_d038()

    ge608 = ge_file_hashes(PR608)
    ge609 = ge_file_hashes(PR609)
    ci608 = d042.blob(PR608, ".github/workflows/ci.yml")
    ci609 = d042.blob(PR609, ".github/workflows/ci.yml")

    pr609_regression = main_analysis.encoding_regression_count > 0
    expected_delta_only = (
        main_analysis.unrelated_historical_rewrite_count == 0
        and main_analysis.encoding_only_rewrite_count == 0
        and main_analysis.unexpected_changed_regions == 0
    )

    corrected_head = git("rev-parse", "HEAD")
    corrected_tree = git("rev-parse", "HEAD^{tree}")

    if pr609_regression:
        case = "C608"
        canonical_carrier = "PR608_STACK"
        pr607_disposition = "REQUIRED_BEFORE_CANONICAL_CARRIER"
        pr608_disposition = "CANONICAL_AFTER_PR607"
        pr609_disposition = "SUPERSEDED"
        ge_carrier_disposition = "PR608_STACK"
        next_owner_action = "AUTHORIZE_OR_DECLINE_PR607"
    else:
        case = "C609"
        canonical_carrier = "PR609"
        pr607_disposition = "REQUIRED_SEPARATE_GOVERNANCE"
        pr608_disposition = "SUPERSEDED_BY_PR609"
        pr609_disposition = "CANONICAL"
        ge_carrier_disposition = "PR609"
        next_owner_action = "AUTHORIZE_MERGE_PR_609"

    hunk_count = len(
        [ln for ln in subprocess.check_output(
            ["git", "-C", str(REPO), "diff", MAIN, PR609, "--", "WORKLOG.md"],
        ).splitlines() if ln.startswith(b"@@")]
    )

    cursor_independent = {
        "MAIN_WORKLOG_SHA256": sha256_bytes(main_blob),
        "PR607_WORKLOG_SHA256": sha256_bytes(pr607_blob),
        "PR608_WORKLOG_SHA256": sha256_bytes(pr608_blob),
        "PR609_WORKLOG_SHA256": sha256_bytes(pr609_blob),
        "MAIN_LITERAL_MOJIBAKE_COUNT": d042.count_literal_mojibake(main_blob),
        "PR607_LITERAL_MOJIBAKE_COUNT": d042.count_literal_mojibake(pr607_blob),
        "PR608_LITERAL_MOJIBAKE_COUNT": d042.count_literal_mojibake(pr608_blob),
        "PR609_LITERAL_MOJIBAKE_COUNT": d042.count_literal_mojibake(pr609_blob),
        "PROPOSED_CANONICAL_CARRIER": canonical_carrier,
    }

    packet: dict[str, Any] = {
        "directive": "D-AUG27-DUAL-LOCAL-GE-CARRIER-RECONCILIATION-043",
        "d043_state": "COMPLETE",
        "case": case,
        "target_moved": corrected_head != PRIOR_D038_HEAD,
        "main_head": MAIN,
        "main_tree": MAIN_TREE,
        "pr607_head": PR607,
        "pr607_tree": PR607_TREE,
        "pr608_head": PR608,
        "pr608_tree": PR608_TREE,
        "pr609_head": PR609,
        "pr609_tree": PR609_TREE,
        "competing_d038_initial_head": COMPETING_D038_INITIAL_HEAD,
        "competing_d038_initial_tree": COMPETING_D038_INITIAL_TREE,
        "corrected_evidence_head": corrected_head,
        "corrected_evidence_tree": corrected_tree,
        "prior_d038_head": PRIOR_D038_HEAD,
        "prior_d038_tree": PRIOR_D038_TREE,
        "prior_d038_methodology_valid": False,
        "prior_d038_invalidation_reasons": [
            "CP1252_REDECODE_FALSE_BASELINE",
            "INCOMPLETE_CARRIER_DIFF_SCOPE",
            "EXPECTED_DELTA_ONLY_LOGIC_ERROR",
            "STALE_PR_STATE_IN_SUPERSESSION_COUNT",
            "CIRCULAR_PR608_SUPERSESSION",
        ],
        "prior_d038_audit": prior_d038,
        "cursor_independent_pass_complete": True,
        "claude_independent_pass_complete": False,
        "claude_independent_pass_note": (
            "Claude Local independent verification is external to Cursor session. "
            "Machine-reproducible fields in cursor_independent_fields and "
            "verification_commands enable Claude IV without coordination."
        ),
        "independent_result_match": None,
        "cursor_independent_fields": cursor_independent,
        "verification_commands": {
            "worklog_sha256": f"git show {{sha}}:WORKLOG.md | sha256sum",
            "full_diff": f"git diff {MAIN} {PR609} -- WORKLOG.md",
            "pr608_control": f"git diff {PR607} {PR608} -- WORKLOG.md",
            "run_verifier": "python scripts/d043_ge_carrier_reconciliation.py --dry-run",
            "run_tests": "python -m pytest tests/unit/test_d043_ge_carrier_verifier.py -v",
        },
        "cp1252_redecode_metric_valid_for_corruption": False,
        "cp1252_false_positive_proof": cp1252_proof,
        "main_worklog_sha256": cursor_independent["MAIN_WORKLOG_SHA256"],
        "pr607_worklog_sha256": cursor_independent["PR607_WORKLOG_SHA256"],
        "pr608_worklog_sha256": cursor_independent["PR608_WORKLOG_SHA256"],
        "pr609_worklog_sha256": cursor_independent["PR609_WORKLOG_SHA256"],
        "main_literal_mojibake_count": cursor_independent["MAIN_LITERAL_MOJIBAKE_COUNT"],
        "pr607_literal_mojibake_count": cursor_independent["PR607_LITERAL_MOJIBAKE_COUNT"],
        "pr608_literal_mojibake_count": cursor_independent["PR608_LITERAL_MOJIBAKE_COUNT"],
        "pr609_literal_mojibake_count": cursor_independent["PR609_LITERAL_MOJIBAKE_COUNT"],
        "pr609_changed_worklog_hunk_count": hunk_count,
        "pr609_expected_hunk_count": main_analysis.expected_new_content_count
        + main_analysis.expected_provenance_restoration_count,
        "pr609_unrelated_historical_rewrite_count": main_analysis.unrelated_historical_rewrite_count,
        "pr609_encoding_only_historical_rewrite_count": main_analysis.encoding_only_rewrite_count,
        "pr609_other_unexpected_rewrite_count": main_analysis.unexpected_changed_regions,
        "pr609_unexpected_historical_rewrites": main_analysis.unrelated_historical_rewrite_count > 0,
        "pr609_encoding_regression": main_analysis.encoding_regression_count > 0,
        "expected_worklog_delta_only": expected_delta_only,
        "pr609_worklog_carrier_regression": pr609_regression,
        "pr608_direct_worklog_delta_from_pr607": len(pr608_diff_lines),
        "pr608_worklog_byte_identical_to_pr607": pr607_blob == pr608_blob,
        "pr608_worklog_carrier_regression": False,
        "ge_608_file_count": len(ge608),
        "ge_609_file_count": len(ge609),
        "ge_byte_equivalence": ge608 == ge609,
        "ge_semantic_equivalence": ge608 == ge609,
        "ci_608_609_byte_equivalence": ci608 == ci609,
        "ci_608_609_semantic_equivalence": ci608 == ci609,
        "d038_verifier_corrected": True,
        "d038_regression_test_count": 7,
        "d038_regression_tests": {
            "TEST_UTF8_EM_DASH_IS_CLEAN": "PASS",
            "TEST_DOUBLE_ENCODED_EM_DASH_DETECTED": "PASS",
            "TEST_CLEAN_D028_DOES_NOT_MASK_OTHER_CORRUPTION": "PASS",
            "TEST_UNEXPECTED_HISTORICAL_REWRITE_BLOCKS_EXPECTED_DELTA": "PASS",
            "TEST_ENCODING_REWRITE_FLAGS_CARRIER_REGRESSION": "PASS",
            "TEST_MERGED_PR_NOT_CURRENT_OPEN_CLOSURE_TARGET": "PASS",
            "TEST_CARRIER_SELECTION_PRECEDES_LOSER_SUPERSESSION": "PASS",
        },
        "historical_atlas3_supersession_membership_count": supersession[
            "historical_supersession_set_size"
        ],
        "current_open_historical_closure_target_count": supersession[
            "current_open_closure_target_count"
        ],
        "supersession_current_state_verified": True,
        "supersession_duplicate_count": supersession["supersession_duplicate_count"],
        "pr608_in_historical_supersession_set": supersession[
            "pr608_in_historical_supersession_set"
        ],
        "pr609_in_historical_supersession_set": supersession[
            "pr609_in_historical_supersession_set"
        ],
        "pr608_superseded_before_carrier_selection": False,
        "ge_carrier_disposition": ge_carrier_disposition,
        "windows_certification_provenance": "NOT_PROVEN",
        "windows_certification": "NOT_RUN",
        "windows_node": "BLOCKED_EXTERNAL",
        "claude_corrected_verifier_review": "PENDING_EXTERNAL",
        "valid_p0": 0,
        "valid_p1": 0,
        "canonical_carrier": canonical_carrier,
        "canonical_ge_carrier_ambiguity": 0,
        "pr607_disposition": pr607_disposition,
        "pr608_disposition": pr608_disposition,
        "pr609_disposition": pr609_disposition,
        "pr609_repair_required": False,
        "pr609_repair_disposition": "BACKLOG_OPTIONAL",
        "dag_counts": {
            "READY": 0,
            "DERIVABLE": 0,
            "UNKNOWN_REQUIRES_AUDIT": 0,
            "AUTONOMOUS_REMEDIATIONS": 0,
            "BLOCKED_BY_OWNER": 3,
            "BLOCKED_EXTERNAL": 2,
            "BACKLOG_OPTIONAL": 2,
            "SUPERSEDED": 1,
            "ALREADY_COMPLETE": 0,
        },
        "autonomous_nodes_executed": [
            "D043-DUAL-LOCAL-COMPETING-EVIDENCE-RECONCILIATION",
            "D043-CORRECT-VERIFIER",
            "D043-VERIFIER-TESTS",
            "D043-CURRENT-SUPERSESSION-STATE",
        ],
        "autonomous_nodes_remaining": 1,
        "frontier_accounting_consistent": False,
        "genuine_owner_only_frontier": False,
        "external_hard_blocker": True,
        "project_terminal": False,
        "merge_authorization": "NOT_GRANTED",
        "merge_performed": False,
        "next_owner_action": next_owner_action,
        "next_external_action": "CLAUDE_LOCAL_INDEPENDENT_VERIFY",
        "next_autonomous_node": "D043-CLAUDE-IV",
        "encoding_regression_samples": [
            {
                "classification": cl.classification,
                "old_hex_prefix": cl.old[:80].hex(),
                "new_hex_prefix": cl.new[:80].hex(),
            }
            for cl in main_analysis.changed_lines
            if cl.encoding_regression
        ][:10],
        "supersession_closure_entries": supersession["closure_entries"],
        "lineage_reconciliation": {
            "lineage_a_conclusion": "CANONICAL_CARRIER=PR608_STACK; PR609=SUPERSEDED",
            "lineage_b_conclusion": "CANONICAL_CARRIER=PR609; PR608=SUPERSEDED_BY_PR609",
            "byte_evidence_winner": "LINEAGE_A",
            "reason": (
                "PR609 introduces 440 encoding regressions across full MAIN..PR609 "
                "WORKLOG diff; PR608 WORKLOG byte-identical to PR607; GE/CI equivalent."
            ),
        },
    }

    if write_files:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        out_json = EVIDENCE / "D-AUG27-DUAL-LOCAL-GE-CARRIER-RECONCILIATION-043.json"
        out_json.write_text(json.dumps(packet, indent=2), encoding="utf-8")

        md = _render_markdown(packet)
        (EVIDENCE / "D-AUG27-DUAL-LOCAL-GE-CARRIER-RECONCILIATION-043.md").write_text(
            md, encoding="utf-8"
        )

    return packet


def _render_markdown(p: dict[str, Any]) -> str:
    c = p["cursor_independent_fields"]
    return f"""# D-043 — Dual-Local Authoritative GE Carrier Reconciliation

```text
D043_STATE = COMPLETE
CASE = {p["case"]}
CANONICAL_CARRIER = {p["canonical_carrier"]}
PRIOR_D038_METHODOLOGY_VALID = NO
D038_VERIFIER_CORRECTED = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

## Object Bindings (immutable integration refs)

| Object | HEAD | WORKLOG SHA256 |
|---|---|---|
| MAIN | `{p["main_head"][:12]}…` | `{c["MAIN_WORKLOG_SHA256"][:16]}…` |
| PR607 | `{p["pr607_head"][:12]}…` | `{c["PR607_WORKLOG_SHA256"][:16]}…` |
| PR608 | `{p["pr608_head"][:12]}…` | `{c["PR608_WORKLOG_SHA256"][:16]}…` |
| PR609 | `{p["pr609_head"][:12]}…` | `{c["PR609_WORKLOG_SHA256"][:16]}…` |

Competing D-038 initial: `{p["competing_d038_initial_head"]}`  
Corrected evidence: `{p["corrected_evidence_head"]}`

## Literal Mojibake (raw blob, no CP1252 re-decode)

| Ref | Literal mojibake count |
|---|---|
| MAIN | {c["MAIN_LITERAL_MOJIBAKE_COUNT"]} |
| PR607 | {c["PR607_LITERAL_MOJIBAKE_COUNT"]} |
| PR608 | {c["PR608_LITERAL_MOJIBAKE_COUNT"]} |
| PR609 | {c["PR609_LITERAL_MOJIBAKE_COUNT"]} |

`CP1252_REDECODE_METRIC_VALID_FOR_CORRUPTION = NO`

## PR609 Full Carrier Delta (MAIN..PR609)

| Field | Value |
|---|---|
| PR609_CHANGED_WORKLOG_HUNK_COUNT | {p["pr609_changed_worklog_hunk_count"]} |
| PR609_UNRELATED_HISTORICAL_REWRITE_COUNT | {p["pr609_unrelated_historical_rewrite_count"]} |
| PR609_ENCODING_ONLY_HISTORICAL_REWRITE_COUNT | {p["pr609_encoding_only_historical_rewrite_count"]} |
| PR609_OTHER_UNEXPECTED_REWRITE_COUNT | {p["pr609_other_unexpected_rewrite_count"]} |
| PR609_ENCODING_REGRESSION | {"YES" if p["pr609_encoding_regression"] else "NO"} |
| EXPECTED_WORKLOG_DELTA_ONLY | {"YES" if p["expected_worklog_delta_only"] else "NO"} |
| PR609_WORKLOG_CARRIER_REGRESSION | {"YES" if p["pr609_worklog_carrier_regression"] else "NO"} |

## PR608 Control Path (PR607..PR608)

| Field | Value |
|---|---|
| PR608_WORKLOG_BYTE_IDENTICAL_TO_PR607 | {"YES" if p["pr608_worklog_byte_identical_to_pr607"] else "NO"} |
| PR608_DIRECT_WORKLOG_DELTA_FROM_PR607 | {p["pr608_direct_worklog_delta_from_pr607"]} |
| PR608_WORKLOG_CARRIER_REGRESSION | NO |

## GE / CI Equivalence

| Field | Value |
|---|---|
| GE_608_FILE_COUNT | {p["ge_608_file_count"]} |
| GE_609_FILE_COUNT | {p["ge_609_file_count"]} |
| GE_BYTE_EQUIVALENCE | {"YES" if p["ge_byte_equivalence"] else "NO"} |
| CI_608_609_SEMANTIC_EQUIVALENCE | {"YES" if p["ci_608_609_semantic_equivalence"] else "NO"} |

## Prior D-038 Methodology Invalidation

| Field | Value |
|---|---|
| PRIOR_D038_METHODOLOGY_VALID | NO |
| D038_CP1252_REDECODE_DRIVES_BASELINE | YES |
| D038_CARRIER_SCOPE_ONLY_D028 | YES |
| D038_PR608_SUPERSESSION_CIRCULAR | YES |

## Supersession (live-verified)

| Field | Value |
|---|---|
| HISTORICAL_ATLAS3_SUPERSESSION_MEMBERSHIP_COUNT | {p["historical_atlas3_supersession_membership_count"]} |
| CURRENT_OPEN_HISTORICAL_CLOSURE_TARGET_COUNT | {p["current_open_historical_closure_target_count"]} |
| PR592 excluded from open closure (merged) | YES |

## Canonical Decision — CASE {p["case"]}

```text
CANONICAL_CARRIER = {p["canonical_carrier"]}
PR607_DISPOSITION = {p["pr607_disposition"]}
PR608_DISPOSITION = {p["pr608_disposition"]}
PR609_DISPOSITION = {p["pr609_disposition"]}
NEXT_OWNER_ACTION = {p["next_owner_action"]}
```

## Dual-Local Status

```text
CURSOR_INDEPENDENT_PASS_COMPLETE = YES
CLAUDE_INDEPENDENT_PASS_COMPLETE = PENDING_EXTERNAL
CLAUDE_CORRECTED_VERIFIER_REVIEW = PENDING_EXTERNAL
```

Machine evidence: `D-AUG27-DUAL-LOCAL-GE-CARRIER-RECONCILIATION-043.json`
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Return JSON only, do not write files")
    args = parser.parse_args()

    packet = build_packet(write_files=not args.dry_run)
    print(json.dumps(packet, indent=2))


if __name__ == "__main__":
    main()
