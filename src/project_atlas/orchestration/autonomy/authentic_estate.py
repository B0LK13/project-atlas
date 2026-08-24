"""D-148 / D-149 — AUTHENTIC_ESTATE_ROOT preflight and non-escalating consumption.

D-149 invariant: authentic estate availability may satisfy an estate/input
prerequisite. It must never grant owner authority or rewrite unrelated gates.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from project_atlas.pilot_auth_prep import MARKER, is_fixture_or_temp_marker

PACKAGE_ID: Final[str] = "AS-D148-AUTHENTIC-ESTATE-001"
D149_PACKAGE_ID: Final[str] = "AS-D149-OWNER-GATE-NON-ESCALATION-001"
_CREDENTIAL_REL = Path(".atlas/orchestration/sdk-runtime/d148-authentic-estate-credential.json")
_PLACEHOLDER_ROOTS: Final[frozenset[str]] = frozenset(
    {"<ABSOLUTE_REAL_PROJECT_PATH>", "<absolute_real_project_path>"}
)
_NON_AUTHENTIC_FRAGMENTS: Final[tuple[str, ...]] = (
    "/tests/fixtures/",
    "\\tests\\fixtures\\",
    "/fixtures/demo/",
    "\\fixtures\\demo\\",
    "/fixtures/pilots/",
    "\\fixtures\\pilots\\",
    "harbor-api",
    "synthetic",
)
AUTHENTIC_ESTATE_DEPENDENCY: Final[str] = "AUTHENTIC_ESTATE_ROOT"
CONSUMABLE_OWNER_GATE: Final[str] = "CREDENTIAL"
PROTECTED_OWNER_GATES: Final[frozenset[str]] = frozenset(
    {
        "MERGE",
        "SECURITY",
        "HUMAN",
        "OWNER",
        "RELEASE",
        "GOVERNOR",
        "SIGNOFF",
    }
)


class EstatePreflight(BaseModel):
    """Read-only preflight for an owner-supplied estate root."""

    model_config = ConfigDict(extra="forbid")

    package_id: str = PACKAGE_ID
    root: str
    root_exists: bool = False
    root_is_directory: bool = False
    root_is_authentic: bool = False
    root_is_not_atlas_fixture: bool = False
    root_is_not_test_fixture: bool = False
    root_is_not_synthetic_demo: bool = False
    root_is_readable: bool = False
    has_project_marker: bool = False
    project_id: str | None = None
    project_uuid: str | None = None
    preflight_pass: bool = False
    estate_fingerprint: str | None = None


class OrchestrationSnapshot(BaseModel):
    """Byte snapshot of durable orchestration files that estate mutation may touch."""

    model_config = ConfigDict(extra="forbid")

    nodes_text: str | None = None
    credential_text: str | None = None
    objectives_text: str | None = None
    cert_text: str | None = None
    checkpoint_text: str | None = None
    mission_state_text: str | None = None


class AuthenticO2PreflightError(RuntimeError):
    """Fail-closed pre-mutation guard. No durable authority widening occurred."""


def _rt(root: Path) -> Path:
    return root / ".atlas" / "orchestration" / "sdk-runtime"


def estate_prerequisite_consumable(
    *,
    owner_gate: str,
    dependencies: Sequence[str],
) -> bool:
    """True only for CREDENTIAL nodes waiting on AUTHENTIC_ESTATE_ROOT (D-149)."""
    if owner_gate in PROTECTED_OWNER_GATES:
        return False
    if owner_gate != CONSUMABLE_OWNER_GATE:
        return False
    return AUTHENTIC_ESTATE_DEPENDENCY in list(dependencies)


def consume_satisfied_estate_dependency(dependencies: Sequence[str]) -> list[str]:
    """Remove only AUTHENTIC_ESTATE_ROOT; preserve every other dependency."""
    return [item for item in dependencies if item != AUTHENTIC_ESTATE_DEPENDENCY]


def remaining_credential_dependencies(dependencies: Sequence[str]) -> list[str]:
    """Non-package dependencies still represent credentials/capabilities."""
    return [item for item in dependencies if not item.startswith("AS-")]


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _repo_git_pin(repo_root: Path) -> tuple[str, str]:
    try:
        head_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if head_proc.returncode != 0:
            return "", ""
        head = head_proc.stdout.strip()
        tree_proc = subprocess.run(
            ["git", "rev-parse", f"{head}^{{tree}}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        tree = tree_proc.stdout.strip() if tree_proc.returncode == 0 else ""
        return head, tree
    except OSError:
        return "", ""


def load_estate_credential(repo_root: Path) -> dict[str, Any]:
    path = repo_root / _CREDENTIAL_REL
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def estate_credential_binding_current(
    credential: Mapping[str, Any],
    *,
    estate_root: Path,
    preflight: EstatePreflight,
    repo_root: Path,
) -> bool:
    """Reject stale/cross-project/cross-head credential bindings (D-149).

    A present credential is fail-closed: missing estate root, fingerprint, or
    live-main pin cannot be treated as current. Absence of a credential file is
    handled by the caller (env/preflight may still satisfy the estate input).
    """
    if not credential:
        return False
    recorded_root = str(
        credential.get("AUTHENTIC_ESTATE_ROOT") or credential.get("root") or ""
    ).strip()
    if not recorded_root:
        return False
    try:
        if Path(recorded_root).resolve() != estate_root.resolve():
            return False
    except OSError:
        return False
    recorded_fp = str(credential.get("estate_fingerprint") or "").strip()
    current_fp = str(preflight.estate_fingerprint or "").strip()
    if not recorded_fp or not current_fp or recorded_fp != current_fp:
        return False
    recorded_project = str(credential.get("project_id") or "").strip()
    if recorded_project and preflight.project_id and recorded_project != preflight.project_id:
        return False
    recorded_uuid = str(credential.get("project_uuid") or "").strip()
    if recorded_uuid and preflight.project_uuid and recorded_uuid != preflight.project_uuid:
        return False
    recorded_head = str(credential.get("live_main_head") or "").strip()
    live_head, _live_tree = _repo_git_pin(repo_root)
    # D-149R5: a present credential is fail-closed without a resolvable git HEAD.
    # Missing live identity must not be treated as "no pin to check".
    if not live_head or len(live_head) != 40:
        return False
    if not recorded_head or len(recorded_head) != 40:
        return False
    if recorded_head != live_head:
        from project_atlas.orchestration.autonomy.exact_main_closure import (
            is_ancestor,
            is_metadata_only_post_cert_delta,
        )

        if not (
            is_ancestor(repo_root, recorded_head, live_head)
            and is_metadata_only_post_cert_delta(repo_root, recorded_head, live_head)
        ):
            return False
    return True


def _read_optional_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _restore_optional_text(path: Path, text: str | None) -> None:
    if text is None:
        if path.is_file():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def snapshot_orchestration_state(repo_root: Path) -> OrchestrationSnapshot:
    runtime = _rt(repo_root)
    return OrchestrationSnapshot(
        nodes_text=_read_optional_text(runtime / "mission-nodes.json"),
        credential_text=_read_optional_text(repo_root / _CREDENTIAL_REL),
        objectives_text=_read_optional_text(runtime / "mission-objectives.json"),
        cert_text=_read_optional_text(runtime / "d148-o2-certification.json"),
        checkpoint_text=_read_optional_text(runtime / "d148-checkpoint.json"),
        mission_state_text=_read_optional_text(runtime / "mission-reconciler-state.json"),
    )


def restore_orchestration_state(repo_root: Path, snapshot: OrchestrationSnapshot) -> None:
    runtime = _rt(repo_root)
    _restore_optional_text(runtime / "mission-nodes.json", snapshot.nodes_text)
    _restore_optional_text(repo_root / _CREDENTIAL_REL, snapshot.credential_text)
    _restore_optional_text(runtime / "mission-objectives.json", snapshot.objectives_text)
    _restore_optional_text(runtime / "d148-o2-certification.json", snapshot.cert_text)
    _restore_optional_text(runtime / "d148-checkpoint.json", snapshot.checkpoint_text)
    _restore_optional_text(
        runtime / "mission-reconciler-state.json", snapshot.mission_state_text
    )


def resolve_authentic_estate_root(
    repo_root: Path,
    *,
    explicit: str | None = None,
) -> Path | None:
    """Resolve canonical estate path from explicit arg, env, or credential file."""
    candidates: list[str] = []
    if explicit and explicit.strip():
        candidates.append(explicit.strip())
    env = os.environ.get("AUTHENTIC_ESTATE_ROOT", "").strip()
    if env:
        candidates.append(env)
    cred_path = _rt(repo_root) / "d148-authentic-estate-credential.json"
    if cred_path.is_file():
        try:
            data = json.loads(cred_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                raw = str(data.get("AUTHENTIC_ESTATE_ROOT") or data.get("root") or "")
                if raw:
                    candidates.append(raw)
        except (OSError, json.JSONDecodeError):
            pass
    for raw in candidates:
        if raw in _PLACEHOLDER_ROOTS:
            continue
        path = Path(raw)
        if path.is_dir():
            return path.resolve()
    return None


_FINGERPRINT_EXCLUDE_DIRS: Final[frozenset[str]] = frozenset(
    {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", ".atlas"}
)
_FINGERPRINT_FILE_CAP: Final[int] = 5000


def estate_fingerprint(estate_root: Path) -> str:
    """Bind estate identity to marker + source corpus, not the marker alone.

    A document edit that leaves `.atlas-project.yaml` unchanged must change
    the fingerprint so D-148/D-149 evidence cannot stay current on a drifted
    corpus (AS-D148-ESTATE-CORPUS-FINGERPRINT-001).
    """
    import hashlib

    root = estate_root.resolve()
    digest = hashlib.sha256()
    marker = root / MARKER
    if marker.is_file():
        digest.update(b"marker:")
        digest.update(marker.read_bytes())
    collected: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in _FINGERPRINT_EXCLUDE_DIRS for part in rel.parts):
            continue
        collected.append(path)
    collected.sort(key=lambda item: item.relative_to(root).as_posix())
    if _FINGERPRINT_FILE_CAP < 1:
        raise ValueError("estate fingerprint file cap must be positive")
    # D-149R5: inventory + full streamed content hash. The cap is a
    # positivity guard / test seam, not a license to skip overflow bytes.
    digest.update(b"inventory-count:")
    digest.update(str(len(collected)).encode("ascii"))
    digest.update(b"\n")
    for path in collected:
        rel_posix = path.relative_to(root).as_posix()
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        digest.update(rel_posix.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\n")
    for path in collected:
        rel_posix = path.relative_to(root).as_posix()
        digest.update(b"content:")
        digest.update(rel_posix.encode("utf-8"))
        digest.update(b"\0")
        file_digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                file_digest.update(chunk)
        digest.update(file_digest.digest())
    return digest.hexdigest()


def d148_evidence_applies(
    evidence: dict[str, Any],
    main_head: str,
    repo_root: Path,
) -> bool:
    """D-148 certification applies only to current main head and estate identity.

    Fail-closed: missing estate root, missing fingerprint, empty current
    fingerprint, or any mismatch rejects the packet (D-149R2 / D-149R3).
    """
    if not evidence:
        return False
    pin = str(evidence.get("live_main_head") or "")
    if not pin or len(pin) != 40:
        return False
    from project_atlas.orchestration.autonomy.exact_main_closure import (
        cert_evidence_applies_to_head,
        is_ancestor,
        is_metadata_only_post_cert_delta,
    )

    head_ok = pin == main_head or cert_evidence_applies_to_head(
        {"CERTIFICATION_TARGET_HEAD": pin},
        main_head,
        repo_root,
    )
    if not head_ok and is_ancestor(repo_root, pin, main_head):
        head_ok = is_metadata_only_post_cert_delta(repo_root, pin, main_head)
    if not head_ok:
        return False
    estate = resolve_authentic_estate_root(repo_root)
    if estate is None:
        return False
    recorded_root = str(evidence.get("AUTHENTIC_ESTATE_ROOT") or "").strip()
    if not recorded_root:
        return False
    try:
        if str(estate.resolve()) != str(Path(recorded_root).resolve()):
            return False
    except OSError:
        return False
    # D-149R2/R3: certification is fail-closed on estate identity. A missing
    # fingerprint, an unreadable current fingerprint, or a mismatch must
    # reject the packet — never skip-if-absent (AS-D149R2-EVIDENCE-BINDING-001).
    recorded_fp = str(evidence.get("estate_fingerprint") or "").strip()
    if not recorded_fp:
        return False
    current_fp = estate_fingerprint(estate)
    return bool(current_fp) and recorded_fp == current_fp


def run_estate_preflight(estate_root: Path) -> EstatePreflight:
    root = estate_root.resolve()
    marker = root / MARKER
    lowered = str(root).lower()
    not_fixture = not any(frag in lowered for frag in _NON_AUTHENTIC_FRAGMENTS)
    not_demo = "demo" not in lowered or "dev-ai" in lowered
    project_id: str | None = None
    project_uuid: str | None = None
    marker_parse_ok = False
    if marker.is_file():
        try:
            import yaml

            data = yaml.safe_load(marker.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                proj = data.get("project")
                if isinstance(proj, dict):
                    raw_id = str(proj.get("id") or "").strip()
                    if raw_id:
                        project_id = raw_id
                        marker_parse_ok = True
                raw_uuid = str(data.get("project_uuid") or "").strip()
                if raw_uuid:
                    project_uuid = raw_uuid
        except Exception:
            marker_parse_ok = False
    authentic_marker = (
        marker.is_file()
        and marker_parse_ok
        and not is_fixture_or_temp_marker(marker)
    )
    readable = os.access(root, os.R_OK)
    preflight_pass = all(
        [
            root.is_dir(),
            authentic_marker,
            not_fixture,
            not_demo,
            readable,
        ]
    )
    return EstatePreflight(
        root=str(root),
        root_exists=root.exists(),
        root_is_directory=root.is_dir(),
        root_is_authentic=authentic_marker,
        root_is_not_atlas_fixture=not_fixture,
        root_is_not_test_fixture=not_fixture,
        root_is_not_synthetic_demo=not_demo,
        root_is_readable=readable,
        has_project_marker=marker.is_file(),
        project_id=project_id,
        project_uuid=project_uuid,
        preflight_pass=preflight_pass,
        estate_fingerprint=estate_fingerprint(root) if marker.is_file() else None,
    )


def write_estate_credential(repo_root: Path, estate_root: Path, preflight: EstatePreflight) -> Path:
    """Record estate availability. Never derives OWNER_CAPABILITY_GRANTED from FS."""
    path = repo_root / _CREDENTIAL_REL
    live_head, live_tree = _repo_git_pin(repo_root)
    if not live_head or len(live_head) != 40:
        raise AuthenticO2PreflightError(
            "cannot persist estate credential without a resolvable git HEAD"
        )
    available = bool(preflight.preflight_pass)
    payload = {
        "directive": "D-148",
        "d149_non_escalation": True,
        "package_id": D149_PACKAGE_ID,
        "AUTHENTIC_ESTATE_ROOT": str(estate_root.resolve()),
        "AUTHENTIC_ESTATE_ROOT_AVAILABLE": available,
        "OWNER_CAPABILITY_GRANTED": False,
        "owner_capability_source": "none",
        "estate_does_not_grant_owner_authority": True,
        "preflight": preflight.model_dump(),
        "preflight_pass": available,
        "estate_fingerprint": preflight.estate_fingerprint,
        "project_id": preflight.project_id,
        "project_uuid": preflight.project_uuid,
        "live_main_head": live_head or None,
        "live_main_tree": live_tree or None,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "merge_authorized": False,
    }
    _atomic_json(path, payload)
    return path


def authentic_estate_available(repo_root: Path) -> bool:
    estate = resolve_authentic_estate_root(repo_root)
    if estate is None:
        return False
    preflight = run_estate_preflight(estate)
    return preflight.preflight_pass


def authentic_estate_ready_for_orchestration(repo_root: Path) -> bool:
    """Estate input is satisfied only when preflight passes and any present credential binds."""
    estate = resolve_authentic_estate_root(repo_root)
    if estate is None:
        return False
    preflight = run_estate_preflight(estate)
    if not preflight.preflight_pass:
        return False
    cred = load_estate_credential(repo_root)
    if not cred:
        return True
    return estate_credential_binding_current(
        cred,
        estate_root=estate,
        preflight=preflight,
        repo_root=repo_root,
    )


def characterize_estate(estate_root: Path) -> dict[str, Any]:
    root = estate_root.resolve()
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    vcs_root = proc.stdout.strip() if proc.returncode == 0 else None
    manifests: list[str] = []
    for name in ("package.json", "pyproject.toml", "Cargo.toml", "go.mod"):
        if (root / name).is_file():
            manifests.append(name)
    src_dirs = [p.name for p in root.iterdir() if p.is_dir() and p.name in {"src", "lib", "app"}]
    doc_dirs = [p.name for p in root.iterdir() if p.is_dir() and p.name in {"docs", "doc"}]
    file_count = 0
    for _ in root.rglob("*"):
        file_count += 1
        if file_count > 50000:
            break
    return {
        "vcs_root": vcs_root,
        "manifests": manifests,
        "source_directories": src_dirs,
        "documentation_directories": doc_dirs,
        "approx_file_count_cap": file_count,
        "has_node_modules": (root / "node_modules").is_dir(),
        "has_git": (root / ".git").is_dir(),
        "has_atlas_metadata": (root / ".atlas").is_dir(),
    }


AUTHENTIC_O2_PACKAGES: Final[tuple[str, ...]] = (
    "AS-CODER-ALPHA-AUTHENTIC-INGEST-001",
    "AS-CODER-ALPHA-AUTHENTIC-COMPILE-001",
    "AS-CODER-ALPHA-AUTHENTIC-QUERY-001",
)


def _authentic_o2_package_ready(
    package_id: str,
    *,
    ingest_done: bool,
    compile_done: bool,
    query_done: bool,
) -> bool:
    if package_id == "AS-CODER-ALPHA-AUTHENTIC-INGEST-001":
        return not ingest_done
    if package_id == "AS-CODER-ALPHA-AUTHENTIC-COMPILE-001":
        return ingest_done and not compile_done
    if package_id == "AS-CODER-ALPHA-AUTHENTIC-QUERY-001":
        return compile_done and not query_done
    return False


def _load_bound_d148_evidence(repo_root: Path) -> dict[str, Any]:
    cert_path = _rt(repo_root) / "d148-o2-certification.json"
    d148: dict[str, Any] = {}
    if cert_path.is_file():
        try:
            raw = json.loads(cert_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                d148 = raw
        except (OSError, json.JSONDecodeError):
            d148 = {}
    main_head, _tree = _repo_git_pin(repo_root)
    if not d148_evidence_applies(d148, main_head, repo_root):
        return {}
    return d148


def validate_authentic_o2_pre_mutation(
    repo_root: Path,
    estate: Path,
    *,
    integrity: Any | None = None,
) -> EstatePreflight:
    """Validate estate + optional closure integrity before any durable mutation."""
    from project_atlas.orchestration.autonomy.exact_main_closure import (
        closure_integrity_pass,
    )

    if not repo_root.exists():
        raise AuthenticO2PreflightError("repository root missing")
    preflight = run_estate_preflight(estate)
    if not preflight.preflight_pass:
        raise AuthenticO2PreflightError("estate preflight failed")
    if integrity is not None and not closure_integrity_pass(integrity):
        raise AuthenticO2PreflightError("closure integrity failed")
    return preflight


def apply_authentic_estate_mutations(
    repo_root: Path,
    estate: Path,
    preflight: EstatePreflight,
    *,
    integrity: Any | None = None,
) -> list[str]:
    """Write availability credential then refresh eligible nodes; restore on failure.

    Integrity that can invalidate execution is checked before any durable write.
    A failing check is a no-op (no credential, no gate widening).
    """
    from project_atlas.orchestration.autonomy.exact_main_closure import (
        closure_integrity_pass,
    )

    if integrity is not None and not closure_integrity_pass(integrity):
        raise AuthenticO2PreflightError("closure integrity failed")
    if not preflight.preflight_pass:
        raise AuthenticO2PreflightError("estate preflight failed")
    snapshot = snapshot_orchestration_state(repo_root)
    try:
        write_estate_credential(repo_root, estate, preflight)
        return refresh_authentic_o2_node_states(repo_root, integrity=integrity)
    except BaseException:
        restore_orchestration_state(repo_root, snapshot)
        raise


def refresh_authentic_o2_node_states(
    repo_root: Path,
    *,
    integrity: Any | None = None,
) -> list[str]:
    """Consume AUTHENTIC_ESTATE_ROOT on CREDENTIAL nodes only (D-149)."""
    from project_atlas.orchestration.autonomy.exact_main_closure import (
        closure_integrity_pass,
    )
    from project_atlas.orchestration.sdk.mission_reconciler import load_nodes, persist_nodes

    if integrity is not None and not closure_integrity_pass(integrity):
        return []
    if not authentic_estate_available(repo_root):
        return []
    estate = resolve_authentic_estate_root(repo_root)
    if estate is None:
        return []
    preflight = run_estate_preflight(estate)
    if not preflight.preflight_pass:
        return []
    cred = load_estate_credential(repo_root)
    if cred and not estate_credential_binding_current(
        cred,
        estate_root=estate,
        preflight=preflight,
        repo_root=repo_root,
    ):
        return []
    d148 = _load_bound_d148_evidence(repo_root)
    ingest_done = bool(d148.get("AUTHENTIC_INGEST_SATISFIED"))
    compile_done = bool(d148.get("AUTHENTIC_COMPILE_SATISFIED"))
    query_done = bool(d148.get("AUTHENTIC_QUERY_SATISFIED"))
    nodes = load_nodes(repo_root)
    snapshot = snapshot_orchestration_state(repo_root)
    changed: list[str] = []
    try:
        for node in nodes.values():
            if node.PACKAGE_ID not in AUTHENTIC_O2_PACKAGES:
                continue
            if node.status in {"COMPLETED", "READY"}:
                continue
            if not estate_prerequisite_consumable(
                owner_gate=node.OWNER_GATE,
                dependencies=node.DEPENDENCIES,
            ):
                continue
            remaining = consume_satisfied_estate_dependency(node.DEPENDENCIES)
            node.DEPENDENCIES = remaining
            if remaining_credential_dependencies(remaining):
                node.OWNER_GATE = "CREDENTIAL"
            else:
                node.OWNER_GATE = "NONE"
            sequential = _authentic_o2_package_ready(
                node.PACKAGE_ID,
                ingest_done=ingest_done,
                compile_done=compile_done,
                query_done=query_done,
            )
            if sequential and not remaining:
                node.status = "READY"
            changed.append(node.NODE_ID)
        if changed:
            persist_nodes(repo_root, nodes)
    except BaseException:
        restore_orchestration_state(repo_root, snapshot)
        raise
    return changed
