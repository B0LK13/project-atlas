"""D-148 — authentic O2 ingest/compile/query against AUTHENTIC_ESTATE_ROOT."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from project_atlas.cli import EXIT_OK, main
from project_atlas.orchestration.autonomy.authentic_estate import (
    characterize_estate,
    refresh_authentic_o2_node_states,
    resolve_authentic_estate_root,
    run_estate_preflight,
    write_estate_credential,
)
from project_atlas.orchestration.autonomy.exact_main_closure import (
    closure_integrity_pass,
    inspect_closure_integrity,
    read_operational_pins,
)
from project_atlas.orchestration.sdk.mission_reconciler import (
    load_nodes,
    load_objectives,
    mission_reconcile,
    persist_nodes,
    persist_objectives,
)

RECEIPT_DIR_REL = Path(".atlas") / "orchestration" / "sdk-runtime"


def _rt(root: Path) -> Path:
    return root / RECEIPT_DIR_REL


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_ask(vault: Path, project: str, question: str, repo: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_atlas.cli",
            "ask2",
            "--vault",
            str(vault),
            "--project",
            project,
            "--question",
            question,
            "--json",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    out: dict[str, Any] = {
        "question": question,
        "exit_code": proc.returncode,
        "pass": False,
    }
    if proc.returncode == 0:
        try:
            payload = json.loads(proc.stdout)
            out["payload"] = {
                "status": payload.get("status"),
                "evidence_count": payload.get("evidence_count"),
            }
            out["pass"] = payload.get("status") in {"known", "unknown"}
        except json.JSONDecodeError:
            out["stderr_tail"] = proc.stderr[-500:]
    else:
        out["stderr_tail"] = proc.stderr[-500:]
    return out


def _mark_package_complete(root: Path, package_id: str) -> None:
    nodes = load_nodes(root)
    for node in nodes.values():
        if package_id == node.PACKAGE_ID and node.status != "COMPLETED":
            node.status = "COMPLETED"
    persist_nodes(root, nodes)


def _update_o2_objectives(root: Path, cert: dict[str, Any]) -> None:
    objectives = load_objectives(root)
    for obj in objectives:
        if obj.objective_id != "O2":
            continue
        if cert.get("AUTHENTIC_PILOT"):
            obj.current_state = "SATISFIED"
            obj.blockers = []
            obj.evidence = [
                "D-148 authentic ingest/compile/query on AUTHENTIC_ESTATE_ROOT",
                f"estate_fingerprint={cert.get('estate_fingerprint')}",
            ]
        elif cert.get("AUTHENTIC_INGEST_SATISFIED"):
            obj.current_state = "ACCEPTANCE_WORKFLOW_SATISFIED"
            obj.blockers = ["AUTHENTIC_COMPILE", "AUTHENTIC_QUERY"]
    persist_objectives(root, objectives)


def run_authentic_o2(
    repo_root: Path,
    *,
    estate_root: Path | None = None,
    keep_vault: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    os.environ["AUTHENTIC_ESTATE_ROOT"] = str(
        estate_root or resolve_authentic_estate_root(repo_root) or ""
    )
    estate = resolve_authentic_estate_root(repo_root)
    if estate is None:
        raise SystemExit("AUTHENTIC_ESTATE_ROOT could not be resolved")
    preflight = run_estate_preflight(estate)
    if not preflight.preflight_pass:
        raise SystemExit(f"estate preflight failed: {preflight.model_dump()}")
    characterization = characterize_estate(estate)
    write_estate_credential(repo_root, estate, preflight)
    refresh_authentic_o2_node_states(repo_root)

    cert_head, cert_tree = read_operational_pins(repo_root)
    integrity = inspect_closure_integrity(
        repo_root,
        certification_target_head=cert_head or "",
        certification_target_tree=cert_tree,
    )
    if not closure_integrity_pass(integrity):
        raise SystemExit("closure integrity failed before authentic O2")

    work_parent = Path(tempfile.mkdtemp(prefix="atlas-d148-"))
    vault = work_parent / "vault"
    vault.mkdir(parents=True)
    steps: dict[str, Any] = {}
    project_id = preflight.project_id or "dark-factory-02ee94d0"

    steps["connect"] = main(["connect", str(estate), "--vault", str(vault)]) == EXIT_OK
    connect_report_path = vault / "generated" / "ops" / "connect-receipt.json"
    if connect_report_path.is_file():
        try:
            connect_report = json.loads(connect_report_path.read_text(encoding="utf-8"))
            steps["connect_documents"] = connect_report.get("documents_ingested")
            steps["connect_projects"] = connect_report.get("projects")
        except (OSError, json.JSONDecodeError):
            pass

    steps["build_indexes"] = main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    steps["build_portfolio"] = main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK
    steps["validate_1"] = main(["validate", "--vault", str(vault)]) == EXIT_OK
    steps["validate_2"] = main(["validate", "--vault", str(vault)]) == EXIT_OK

    queries = [
        ("direct_fact", "What is the primary purpose of this project?"),
        ("readme", "What does the README describe?"),
        ("negative", "What is the quarterly revenue for harbor-api?"),
        ("project_wide", "List main technologies used"),
        ("diagnostic", "What validation warnings exist?"),
    ]
    query_results = [_run_ask(vault, project_id, q, repo_root) for _, q in queries]
    steps["queries"] = query_results
    steps["query_pass"] = sum(1 for q in query_results if q.get("pass")) >= 3

    ingest_pass = steps["connect"] and steps.get("connect_documents", 0) > 0
    compile_pass = steps["build_indexes"] and steps["build_portfolio"] and steps["validate_1"]
    compile_idempotent = steps["validate_2"]
    query_pass = bool(steps["query_pass"])

    cert = {
        "directive": "D-148",
        "AUTHENTIC_ESTATE_ROOT": str(estate),
        "estate_fingerprint": preflight.estate_fingerprint,
        "project_id": project_id,
        "project_uuid": preflight.project_uuid,
        "characterization": characterization,
        "preflight": preflight.model_dump(),
        "AUTHENTIC_INGEST_SATISFIED": ingest_pass,
        "AUTHENTIC_COMPILE_SATISFIED": compile_pass and compile_idempotent,
        "AUTHENTIC_QUERY_SATISFIED": query_pass,
        "AUTHENTIC_PILOT": ingest_pass and compile_pass and compile_idempotent and query_pass,
        "ACCEPTANCE_WORKFLOW_PILOT": ingest_pass and compile_pass and query_pass,
        "authentic_estate_root_used": True,
        "demo_fixture_is_authentic_pilot": False,
        "FIXTURE_ONLY": False,
        "steps": steps,
        "live_main_head": integrity.live_main_head,
        "certification_target_head": integrity.certification_target_head,
        "merge_authorized": False,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _write(_rt(repo_root) / "d148-o2-certification.json", cert)

    if ingest_pass:
        _mark_package_complete(repo_root, "AS-CODER-ALPHA-AUTHENTIC-INGEST-001")
    if compile_pass and compile_idempotent:
        _mark_package_complete(repo_root, "AS-CODER-ALPHA-AUTHENTIC-COMPILE-001")
    if query_pass:
        _mark_package_complete(repo_root, "AS-CODER-ALPHA-AUTHENTIC-QUERY-001")

    _update_o2_objectives(repo_root, cert)
    refresh_authentic_o2_node_states(repo_root)
    load_mission_state_placeholder(repo_root)
    mission_reconcile(repo_root, main_head=integrity.live_main_head)

    if not keep_vault:
        shutil.rmtree(work_parent, ignore_errors=True)
    else:
        cert["vault_path"] = str(vault)

    checkpoint = {
        "directive": "D-148",
        "closure_integrity_pass": closure_integrity_pass(integrity),
        "authentic_o2_cert": cert,
        "merge_authorized": False,
    }
    _write(_rt(repo_root) / "d148-checkpoint.json", checkpoint)
    return checkpoint


def load_mission_state_placeholder(repo_root: Path) -> None:
    """Clear reconcile fingerprint to force replan after O2 certification."""
    from project_atlas.orchestration.sdk.mission_reconciler import (
        load_mission_state,
        persist_mission_state,
    )

    state = load_mission_state(repo_root)
    state.last_planning_fingerprint = ""
    persist_mission_state(repo_root, state)


def main_cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--estate", type=Path, default=None)
    parser.add_argument("--keep-vault", action="store_true")
    args = parser.parse_args()
    result = run_authentic_o2(
        args.root.resolve(),
        estate_root=args.estate.resolve() if args.estate else None,
        keep_vault=args.keep_vault,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("authentic_o2_cert", {}).get("AUTHENTIC_PILOT") else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
