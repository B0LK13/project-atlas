"""D-148 — authentic O2 ingest/compile/query against AUTHENTIC_ESTATE_ROOT."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from project_atlas.bitemporal_catalog import build_bitemporal_catalogs
from project_atlas.cli import EXIT_OK, main
from project_atlas.orchestration.autonomy.authentic_estate import (
    characterize_estate,
    marker_fingerprint,
    refresh_authentic_o2_node_states,
    resolve_authentic_estate_root,
    restore_o2_node_snapshot,
    run_estate_preflight,
    snapshot_o2_nodes,
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
from project_atlas.portfolio import build_portfolio

RECEIPT_DIR_REL = Path(".atlas") / "orchestration" / "sdk-runtime"
BIND_RELATIVE = Path(".atlas") / "connect.json"


def _rt(root: Path) -> Path:
    return root / RECEIPT_DIR_REL


def _estate_query_subject(estate: Path, project_id: str | None) -> str:
    """Derive a contentful ask2 subject from the estate marker (not WH-scaffolding).

    Ask2 claim grounding ignores interrogative scaffolding (purpose/describe/…).
    Certification probes must therefore include a discriminative corpus subject
    such as the project name; otherwise required_terms is empty and answers stay
    unknown by design.
    """
    marker = estate / ".atlas-project.yaml"
    if marker.is_file():
        try:
            import yaml

            data = yaml.safe_load(marker.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                proj = data.get("project")
                if isinstance(proj, dict):
                    name = str(proj.get("name") or "").strip()
                    if name:
                        return name
        except (OSError, ImportError, ValueError, TypeError):
            pass
    if project_id:
        # Prefer human stem when id looks like ``name-<hex>``.
        stem, _, suffix = project_id.rpartition("-")
        if stem and suffix and len(suffix) >= 6 and all(
            ch in "0123456789abcdef" for ch in suffix.lower()
        ):
            return stem
        return project_id
    return estate.name


def _authentic_query_probes(subject: str) -> list[tuple[str, str, bool]]:
    """Build positive/negative ask2 probes with contentful claim anchors.

    Each positive probe must retain discriminative claim terms after
    interrogative-scaffolding removal, and those terms must co-occur in a
    single grounded record (ask2 entailment is per-hit, not corpus-union).
    Prefer short subject+property questions over multi-aspect stacks.
    """
    return [
        ("identity", f"What is {subject}?", False),
        ("purpose", f"What is the purpose of {subject}?", False),
        ("local_first", f"Is {subject} local-first?", False),
        ("negative", "xyzzy plugh nonsense query 0000", True),
        ("mvp", f"Is {subject} an MVP?", False),
    ]


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _hash_generated_tree(vault: Path) -> dict[str, str]:
    generated = vault / "generated"
    if not generated.is_dir():
        return {}
    out: dict[str, str] = {}
    for path in sorted(generated.rglob("*")):
        if path.is_file():
            rel = path.relative_to(generated).as_posix()
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _run_portfolio(vault: Path, *, reference_date: datetime) -> dict[str, Any]:
    """Run portfolio + bitemporal derivation; return contract evidence.

    CLI ``build-portfolio`` always invokes ``build_bitemporal_catalogs``. When
    the corpus declares no validity windows, catalogs may be empty — that is
    still a successful contract exercise (vacuous catalogs), not a compile failure.
    """
    try:
        build_portfolio(vault, reference_date=reference_date)
        catalog = build_bitemporal_catalogs(vault)
        count = int(catalog.get("catalog_count") or 0)
        present = (vault / "generated" / "ops" / "bitemporal").is_dir()
        return {
            "ok": True,
            "catalog_count": count,
            "window_count": int(catalog.get("window_count") or 0),
            "bitemporal_dir_present": present,
            # Vacuous success when no temporal windows exist in the corpus.
            "bitemporal_contract": bool(catalog.get("ok")) and (count == 0 or present),
        }
    except (OSError, ValueError) as exc:
        return {
            "ok": False,
            "error": str(exc),
            "catalog_count": 0,
            "window_count": 0,
            "bitemporal_dir_present": False,
            "bitemporal_contract": False,
        }


def _derive_portfolio_reference_date(vault: Path, *, run_started: datetime) -> datetime:
    """One deterministic reference date per certification run.

    Prefer the latest corpus ``modified_at`` when present so ages are
    non-negative; never use an arbitrary historical constant. Fall back to the
    run start timestamp so rebuilds within the same run stay stable.
    """
    latest = run_started
    manifest = vault / "generated" / "ops" / "connect-manifest.json"
    if not manifest.is_file():
        manifest = vault / "generated" / "discovery" / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            sources = data.get("sources") if isinstance(data, dict) else None
            if isinstance(sources, list):
                for entry in sources:
                    if not isinstance(entry, dict):
                        continue
                    raw = entry.get("modified_at")
                    if not isinstance(raw, str) or not raw:
                        continue
                    try:
                        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=UTC)
                    if ts > latest:
                        latest = ts
        except (OSError, json.JSONDecodeError):
            pass
    return latest


def _run_ask(
    vault: Path,
    project: str,
    question: str,
    repo: Path,
    *,
    expect_unknown: bool = False,
) -> dict[str, Any]:
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
        "expect_unknown": expect_unknown,
        "exit_code": proc.returncode,
        "pass": False,
    }
    if proc.returncode == 0:
        try:
            payload = json.loads(proc.stdout)
            status = payload.get("status")
            evidence_count = int(payload.get("evidence_count") or 0)
            out["payload"] = {
                "status": status,
                "evidence_count": evidence_count,
            }
            if expect_unknown:
                out["pass"] = status == "unknown"
            else:
                out["pass"] = status == "known" and evidence_count > 0
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


def _restore_estate_bind(estate: Path, prior_bind: str | None) -> None:
    bind_path = estate / BIND_RELATIVE
    if prior_bind is not None:
        bind_path.parent.mkdir(parents=True, exist_ok=True)
        bind_path.write_text(prior_bind, encoding="utf-8")
    elif bind_path.is_file():
        bind_path.unlink()


def _snapshot_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _restore_text(path: Path, prior: str | None) -> None:
    if prior is None:
        if path.is_file():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prior, encoding="utf-8")


def run_authentic_o2(
    repo_root: Path,
    *,
    estate_root: Path | None = None,
    keep_vault: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    run_started = datetime.now(UTC)
    prior_estate_env = os.environ.get("AUTHENTIC_ESTATE_ROOT")
    os.environ["AUTHENTIC_ESTATE_ROOT"] = str(
        estate_root or resolve_authentic_estate_root(repo_root) or ""
    )
    try:
        return _run_authentic_o2_body(
            repo_root,
            estate_root=estate_root,
            keep_vault=keep_vault,
            run_started=run_started,
        )
    finally:
        if prior_estate_env is None:
            os.environ.pop("AUTHENTIC_ESTATE_ROOT", None)
        else:
            os.environ["AUTHENTIC_ESTATE_ROOT"] = prior_estate_env


def _run_authentic_o2_body(
    repo_root: Path,
    *,
    estate_root: Path | None,
    keep_vault: bool,
    run_started: datetime,
) -> dict[str, Any]:
    estate = resolve_authentic_estate_root(repo_root)
    if estate is None:
        raise SystemExit("AUTHENTIC_ESTATE_ROOT could not be resolved")
    preflight = run_estate_preflight(estate)
    if not preflight.preflight_pass:
        raise SystemExit(f"estate preflight failed: {preflight.model_dump()}")
    characterization = characterize_estate(estate)

    # Fail-closed: verify closure integrity BEFORE durable DAG authority mutation.
    cert_head, cert_tree = read_operational_pins(repo_root)
    integrity = inspect_closure_integrity(
        repo_root,
        certification_target_head=cert_head or "",
        certification_target_tree=cert_tree,
    )
    if not closure_integrity_pass(integrity):
        raise SystemExit("closure integrity failed before authentic O2")

    rt = _rt(repo_root)
    credential_path = rt / "d148-authentic-estate-credential.json"
    cert_path = rt / "d148-o2-certification.json"
    checkpoint_path = rt / "d148-checkpoint.json"
    nodes_path = rt / "mission-nodes.json"
    objectives_path = rt / "mission-objectives.json"
    mission_state_path = rt / "mission-reconciler-state.json"

    prior_files = {
        "credential": _snapshot_text(credential_path),
        "cert": _snapshot_text(cert_path),
        "checkpoint": _snapshot_text(checkpoint_path),
        "nodes": _snapshot_text(nodes_path),
        "objectives": _snapshot_text(objectives_path),
        "mission_state": _snapshot_text(mission_state_path),
    }
    node_snapshot = snapshot_o2_nodes(repo_root)
    bind_path = estate / BIND_RELATIVE
    prior_bind: str | None = _snapshot_text(bind_path) if bind_path.is_file() else None
    work_parent: Path | None = None
    mutated = False

    def _rollback() -> None:
        restore_o2_node_snapshot(repo_root, node_snapshot)
        _restore_text(credential_path, prior_files["credential"])
        _restore_text(cert_path, prior_files["cert"])
        _restore_text(checkpoint_path, prior_files["checkpoint"])
        _restore_text(nodes_path, prior_files["nodes"])
        _restore_text(objectives_path, prior_files["objectives"])
        _restore_text(mission_state_path, prior_files["mission_state"])
        _restore_estate_bind(estate, prior_bind)
        if work_parent is not None:
            shutil.rmtree(work_parent, ignore_errors=True)

    try:
        write_estate_credential(repo_root, estate, preflight)
        mutated = True
        refresh_authentic_o2_node_states(repo_root)

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

        ingest_pass = bool(steps["connect"]) and int(steps.get("connect_documents") or 0) > 0
        reference_date = _derive_portfolio_reference_date(vault, run_started=run_started)
        steps["portfolio_reference_date"] = reference_date.isoformat()

        if ingest_pass:
            steps["build_indexes"] = main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
            portfolio_1 = _run_portfolio(vault, reference_date=reference_date)
            steps["build_portfolio"] = bool(portfolio_1.get("ok"))
            steps["bitemporal_contract"] = bool(portfolio_1.get("bitemporal_contract"))
            steps["bitemporal_catalog_count"] = int(portfolio_1.get("catalog_count") or 0)
            steps["bitemporal_present"] = bool(portfolio_1.get("bitemporal_dir_present"))
            steps["validate_1"] = main(["validate", "--vault", str(vault)]) == EXIT_OK
            first_hashes = _hash_generated_tree(vault)
            steps["build_indexes_2"] = main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
            portfolio_2 = _run_portfolio(vault, reference_date=reference_date)
            steps["build_portfolio_2"] = bool(portfolio_2.get("ok"))
            second_hashes = _hash_generated_tree(vault)
            steps["validate_2"] = main(["validate", "--vault", str(vault)]) == EXIT_OK
            steps["compile_hash_stable"] = first_hashes == second_hashes and bool(first_hashes)
        else:
            steps["build_indexes"] = False
            steps["build_portfolio"] = False
            steps["bitemporal_contract"] = False
            steps["bitemporal_catalog_count"] = 0
            steps["bitemporal_present"] = False
            steps["validate_1"] = False
            steps["build_indexes_2"] = False
            steps["build_portfolio_2"] = False
            steps["validate_2"] = False
            steps["compile_hash_stable"] = False

        subject = _estate_query_subject(estate, project_id)
        steps["query_subject"] = subject
        queries = _authentic_query_probes(subject)
        query_results = [
            _run_ask(vault, project_id, question, repo_root, expect_unknown=expect_unknown)
            for _, question, expect_unknown in queries
        ]
        steps["queries"] = query_results
        positive_pass = sum(
            1 for q in query_results if not q.get("expect_unknown") and q.get("pass")
        )
        negative_pass = any(
            q.get("expect_unknown") and q.get("pass") for q in query_results
        )
        steps["query_pass"] = positive_pass >= 3 and negative_pass

        compile_pass = ingest_pass and all(
            steps.get(k)
            for k in ("build_indexes", "build_portfolio", "validate_1", "bitemporal_contract")
        )
        compile_idempotent = ingest_pass and bool(steps.get("compile_hash_stable"))
        query_pass = ingest_pass and compile_pass and bool(steps["query_pass"])

        cert = {
            "directive": "D-148",
            "AUTHENTIC_ESTATE_ROOT": str(estate),
            "estate_fingerprint": preflight.estate_fingerprint,
            "marker_fingerprint": marker_fingerprint(estate),
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
            "BITEMPORAL_BUILD_CONTRACT": bool(steps.get("bitemporal_contract")),
            "portfolio_reference_date": reference_date.isoformat(),
            "steps": steps,
            "live_main_head": integrity.live_main_head,
            "certification_target_head": integrity.certification_target_head,
            "merge_authorized": False,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        _write(cert_path, cert)

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
            work_parent = None
            _restore_estate_bind(estate, prior_bind)
        else:
            cert["vault_path"] = str(vault)

        checkpoint = {
            "directive": "D-148",
            "closure_integrity_pass": closure_integrity_pass(integrity),
            "authentic_o2_cert": cert,
            "merge_authorized": False,
        }
        _write(checkpoint_path, checkpoint)
        return checkpoint
    except Exception:
        if mutated:
            _rollback()
        raise


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
