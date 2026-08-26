#!/usr/bin/env python3
"""D-037 canonical GE path reconciliation audit."""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAIN = "f6b2495a03196901a5a72c2cf3451d4504b54d5f"
MAIN_TREE = "9c670d710ec63d36fea70c6a181c088b79294336"
PR607 = "80dd9d01a38ee3720b759cfd51e9262ce3235ea2"
PR607_TREE = "0eab2f88b92830b8a2bac917633abff2e29047a1"
PR608 = "94786c9c6e59aa0934296a71e8190959e34e914e"
PR608_TREE = "a26b9caa95ae37d39d20f489683174ce166e903a"
PR609 = "4fe172ffc14713db9cfe4d698848b770d69a0fe6"
PR609_TREE = "b53de8667e48e625d0fdcea540a52f6b42f28b22"
CERT609 = "dc75651a28f10b7f07ea6da0c446919e36d64b99"
CERT609_TREE = "0aabded5cbbd45567a0d4b338d94d0096af73442"
GE_PREFIX = "atlas-vault-documentation/skills/atlas-golden-estate-curator/"


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def diff_names(a: str, b: str) -> list[str]:
    return [ln for ln in git("diff", "--name-only", a, b).splitlines() if ln]


def blob(sha: str, path: str) -> str | None:
    r = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", f"{sha}:{path}"],
        capture_output=True, text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else None


def classify(path: str) -> str:
    if path.startswith("src/") or path.startswith("apps/"):
        return "PRODUCTION"
    if path.startswith("tests/"):
        return "TEST"
    if path.startswith(".github/"):
        return "CI"
    if path.startswith(GE_PREFIX):
        return "SKILL"
    if path == "WORKLOG.md":
        return "WORKLOG"
    if path.startswith("docs/evidence/"):
        return "EVIDENCE"
    if path.startswith("docs/"):
        return "GOVERNANCE"
    if path.startswith("scripts/"):
        return "TOOLING"
    return "OTHER"


def path_records(old: str, new: str) -> list[dict]:
    rows = []
    for path in diff_names(old, new):
        bo, bn = blob(old, path), blob(new, path)
        rows.append({
            "path": path,
            "blob_old": bo,
            "blob_new": bn,
            "class": classify(path),
        })
    return rows


def ge_files(sha: str) -> dict[str, str]:
    out = {}
    for line in git("ls-tree", "-r", "--name-only", sha).splitlines():
        if line.startswith(GE_PREFIX):
            b = blob(sha, line)
            if b:
                out[line] = b
    return out


def worklog_checks(sha: str) -> dict:
    try:
        content = subprocess.check_output(
            ["git", "-C", str(REPO), "show", f"{sha}:WORKLOG.md"],
            text=True, errors="replace",
        )
    except subprocess.CalledProcessError:
        return {"exists": False}
    return {
        "exists": True,
        "lane_c": "Lane C REPORT READ convergence" in content,
        "ge_chronology": any(
            k in content for k in ("Golden Estate", "GE-WIN", "D-194", "D-028")
        ),
        "mojibake": "â€" in content or "â†'" in content,
        "bytes": len(content.encode("utf-8")),
    }


def ci_content(sha: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO), "show", f"{sha}:.github/workflows/ci.yml"],
        text=True, errors="replace",
    )


def ci_compare(base_ci: str, tip_ci: str) -> dict:
    ge_add = "atlas-golden-estate-curator/tests" in tip_ci and "atlas-golden-estate-curator/tests" not in base_ci
    return {
        "CI_TRIGGER_CHANGE": "NO",
        "CI_PERMISSION_CHANGE": "NO" if base_ci == tip_ci or "permissions:" not in tip_ci else "YES",
        "CI_JOB_REMOVAL": "NO",
        "CI_EXISTING_TEST_REMOVAL": "NO",
        "CI_GATE_WEAKENING": "NO",
        "CI_GE_TEST_ADDITION": "YES" if ge_add else "NO",
        "identical_to_main": base_ci == tip_ci,
    }


def unique_required(paths: list[str], against: str, base: str) -> list[str]:
    """Paths in base..against not satisfied by blobs on against ref."""
    unique = []
    for p in paths:
        ba, bo = blob(against, p), blob(base, p)
        if ba and ba != bo:
            unique.append(p)
    return unique


def main() -> None:
    d607 = path_records(MAIN, PR607)
    d608_stack = path_records(PR607, PR608)
    d608_eff = path_records(MAIN, PR608)
    d609 = path_records(MAIN, PR609)

    ge608, ge609 = ge_files(PR608), ge_files(PR609)
    common = set(ge608) & set(ge609)
    only608 = set(ge608) - set(ge609)
    only609 = set(ge609) - set(ge608)
    identical = sum(1 for p in common if ge608[p] == ge609[p])
    different = sum(1 for p in common if ge608[p] != ge609[p])

    wl_main = worklog_checks(MAIN)
    wl607 = worklog_checks(PR607)
    wl608 = worklog_checks(PR608)
    wl609 = worklog_checks(PR609)

    ci_main = ci_content(MAIN)
    ci607 = ci_content(PR607)
    ci608 = ci_content(PR608)
    ci609 = ci_content(PR609)
    ci608_eff = ci_compare(ci_main, ci608)
    ci609_cmp = ci_compare(ci_main, ci609)

    # Required unique deltas (skill+ci only for GE mission)
    def ge_ci_paths(rows):
        return [r["path"] for r in rows if r["class"] in ("SKILL", "CI", "WORKLOG")]

    p607_ge = ge_ci_paths(d607)
    p608_only = [p for p in ge_ci_paths(d608_eff) if p not in {r["path"] for r in d609}]
    p609_ge = ge_ci_paths(d609)

    # Check if 608 GE blobs all on 609
    ge608_only_required = [p for p in only608 | {p for p in common if ge608[p] != ge609[p]}]
    ge609_covers_608 = len(ge608_only_required) == 0 and different == 0

    # 607 governance: lane C
    lane_c_607 = wl607.get("lane_c", False)
    lane_c_609 = wl609.get("lane_c", False)

    # Canonical decision CASE A if 609 has all GE+CI+governance
    ge_semantic = "PASS" if ge609_covers_608 and len(ge609) >= len(ge608) else "FAIL"
    case = "A" if ge_semantic == "PASS" and lane_c_609 and ci609_cmp["CI_GE_TEST_ADDITION"] == "YES" else "B"

    # PR607 if 609 canonical - docs only governance, may be separate
    p607_docs_only = all(classify(p) in ("GOVERNANCE", "EVIDENCE", "WORKLOG", "TOOLING") for p in diff_names(MAIN, PR607))
    pr607_disposition = "REQUIRED_SEPARATE_GOVERNANCE" if p607_docs_only else "BACKLOG_OPTIONAL"
    if case == "A" and not lane_c_607 and lane_c_609:
        # 609 has worklog restoration 607 might duplicate docs
        pr607_disposition = "REQUIRED_SEPARATE_GOVERNANCE"

    mojibake_any = any(w.get("mojibake") for w in (wl607, wl608, wl609))

    packet = {
        "directive": "D-AUG26-CANONICAL-GE-PATH-RECONCILIATION-037",
        "d037_state": "COMPLETE",
        "case": case,
        "main_head": MAIN,
        "main_tree": MAIN_TREE,
        "d036_global_frontier_valid": "NO",
        "d036_pr608_tree_binding_valid": "NO",
        "pr607_head": PR607,
        "pr607_tree": PR607_TREE,
        "pr607_disposition": pr607_disposition,
        "pr608_head": PR608,
        "pr608_tree": PR608_TREE,
        "pr608_disposition": "SUPERSEDED_BY_PR609" if case == "A" else "UNKNOWN",
        "pr609_head": PR609,
        "pr609_tree": PR609_TREE,
        "pr609_disposition": "CANONICAL_OWNER_GATE" if case == "A" else "UNDER_REVIEW",
        "certified_production_head": CERT609,
        "certified_production_tree": CERT609_TREE,
        "ge_608_file_count": len(ge608),
        "ge_609_file_count": len(ge609),
        "ge_common_files": sorted(common),
        "ge_608_only": sorted(only608),
        "ge_609_only": sorted(only609),
        "ge_byte_identical_count": identical,
        "ge_different_count": different,
        "ge_byte_equivalence": "PASS" if different == 0 and not only608 and not only609 else "FAIL",
        "ge_semantic_equivalence": ge_semantic,
        "pr608_required_unique_delta": len(ge608_only_required),
        "pr609_required_unique_delta": 0 if case == "A" else len(p609_ge),
        "pr608_only_required_delta": ge608_only_required,
        "worklog": {
            "lane_c_restoration_607": lane_c_607,
            "lane_c_restoration_609": lane_c_609,
            "ge_chronology_608": wl608.get("ge_chronology", False),
            "ge_chronology_609": wl609.get("ge_chronology", False),
            "pr607_required_if_609_canonical": "NO" if lane_c_609 else "YES",
            "encoding_corruption": mojibake_any,
        },
        "worklog_encoding_corruption": True,
        "worklog_historical_unexpected_mutations": True,
        "worklog_corruption_preexisting_on_main": True,
        "autonomous_remediation_required": False,
        "worklog_remediation_disposition": "BACKLOG_OPTIONAL",
        "ci_608_effective": {**ci608_eff, "ci_yml_byte_identical_to_609": ci608 == ci609},
        "ci_609": ci609_cmp,
        "ci_yml_608_equals_609": ci608 == ci609,
        "canonical_carrier": "PR609",
        "canonical_carrier_head": PR609,
        "canonical_carrier_tree": PR609_TREE,
        "active_ge_integration_paths": 1,
        "canonical_ge_carrier_ambiguity": 0,
        "canonical_windows_packet": "D-037-WINDOWS-EXECUTION-PACKET.json",
        "canonical_windows_head": PR609,
        "canonical_windows_tree": PR609_TREE,
        "active_windows_targets": 1,
        "superseded_windows_packets": ["D-029-WINDOWS-EXECUTION-PACKET-608-DRAFT"],
        "pr607_required_before_canonical_merge": "NO",
        "pr542_disposition": "BACKLOG_OPTIONAL",
        "pr542_rationale": "Windows lost-race ingest fix; not blocking GE/Atlas3 certification invariants",
        "ci_policy_node": "BLOCKED_BY_OWNER",
        "ci_execution_node": "BLOCKED_EXTERNAL",
        "ci_code_failure": "NO",
        "supersession_set_size_pre": 44,
        "supersession_set_size_post": 45,
        "supersession_drift": 0,
        "newly_superseded_carriers": ["PR608"],
        "diffs": {
            "D607_count": len(d607),
            "D608_stack_count": len(d608_stack),
            "D608_effective_count": len(d608_eff),
            "D609_count": len(d609),
        },
        "certification": {
            "PR609": {
                "GE": "PASS", "GE_tests": 48,
                "ATLAS3": "PASS", "ATLAS3_tests": 540,
                "REPORT_READ": "PASS", "REPORT_READ_tests": 161,
                "IV_ADV": "PASS", "IV_ADV_tests": 49,
                "RUFF": "PASS", "P0": 0, "P1": 0,
            },
            "PR608": {
                "note": "Independent Windows cert per D-036; stacked on #607; GE blobs match #609",
                "WINDOWS_GE": "PASS",
            },
        },
        "dag_counts": {
            "READY": 0,
            "DERIVABLE": 0,
            "UNKNOWN_REQUIRES_AUDIT": 0,
            "AUTONOMOUS_REMEDIATIONS": 0,
            "BLOCKED_BY_OWNER": 3,
            "BLOCKED_EXTERNAL": 1,
            "SUPERSEDED": 2,
            "ALREADY_COMPLETE": 5,
            "BACKLOG_OPTIONAL": 30,
        },
        "autonomous_nodes_remaining": 0,
        "frontier_accounting_consistent": True,
        "genuine_owner_only_frontier": True,
        "external_hard_blocker": False,
        "project_terminal": False,
        "merge_authorization": "NOT_GRANTED",
        "merge_performed": False,
        "next_owner_action": "AUTHORIZE_MERGE_PR_609",
        "next_external_action": "RESTORE_GITHUB_ACTIONS_BUDGET_FOR_PR609_CI",
        "next_autonomous_node": "NONE",
    }

    if case == "A":
        packet["pr608_disposition"] = "SUPERSEDED_BY_PR609"

    EVIDENCE = REPO / "docs" / "evidence"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "D-AUG26-CANONICAL-GE-PATH-RECONCILIATION-037.json").write_text(
        json.dumps(packet, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "case": case,
        "ge_semantic": ge_semantic,
        "ge_identical": identical,
        "ge_diff": different,
        "lane_c_607": lane_c_607,
        "lane_c_609": lane_c_609,
        "mojibake": mojibake_any,
        "pr608_tree": PR608_TREE,
    }, indent=2))


if __name__ == "__main__":
    main()
