"""D-148 — AUTHENTIC_ESTATE_ROOT credential consumption and preflight."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from project_atlas.pilot_auth_prep import MARKER, is_fixture_or_temp_marker

PACKAGE_ID: Final[str] = "AS-D148-AUTHENTIC-ESTATE-001"
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


def _rt(root: Path) -> Path:
    return root / ".atlas" / "orchestration" / "sdk-runtime"


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


def estate_fingerprint(estate_root: Path) -> str:
    marker = estate_root / MARKER
    if marker.is_file():
        import hashlib

        return hashlib.sha256(marker.read_bytes()).hexdigest()
    return ""


def run_estate_preflight(estate_root: Path) -> EstatePreflight:
    root = estate_root.resolve()
    marker = root / MARKER
    lowered = str(root).lower()
    not_fixture = not any(frag in lowered for frag in _NON_AUTHENTIC_FRAGMENTS)
    not_demo = "demo" not in lowered or "dev-ai" in lowered
    authentic_marker = marker.is_file() and not is_fixture_or_temp_marker(marker)
    project_id: str | None = None
    project_uuid: str | None = None
    if marker.is_file():
        try:
            import yaml

            data = yaml.safe_load(marker.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                proj = data.get("project")
                if isinstance(proj, dict):
                    project_id = str(proj.get("id") or "") or None
                project_uuid = str(data.get("project_uuid") or "") or None
        except Exception:
            pass
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
    path = _rt(repo_root) / "d148-authentic-estate-credential.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "directive": "D-148",
        "AUTHENTIC_ESTATE_ROOT": str(estate_root.resolve()),
        "AUTHENTIC_ESTATE_ROOT_AVAILABLE": True,
        "OWNER_CAPABILITY_GRANTED": True,
        "preflight": preflight.model_dump(),
        "preflight_pass": preflight.preflight_pass,
        "estate_fingerprint": preflight.estate_fingerprint,
        "project_id": preflight.project_id,
        "project_uuid": preflight.project_uuid,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "merge_authorized": False,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def authentic_estate_available(repo_root: Path) -> bool:
    estate = resolve_authentic_estate_root(repo_root)
    if estate is None:
        return False
    preflight = run_estate_preflight(estate)
    return preflight.preflight_pass


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


def refresh_authentic_o2_node_states(repo_root: Path) -> list[str]:
    """Unblock O2 credential nodes when estate credential is satisfied (sequential)."""
    from project_atlas.orchestration.sdk.mission_reconciler import load_nodes, persist_nodes

    if not authentic_estate_available(repo_root):
        return []
    cert_path = _rt(repo_root) / "d148-o2-certification.json"
    d148: dict[str, Any] = {}
    if cert_path.is_file():
        try:
            raw = json.loads(cert_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                d148 = raw
        except (OSError, json.JSONDecodeError):
            d148 = {}
    ingest_done = bool(d148.get("AUTHENTIC_INGEST_SATISFIED"))
    compile_done = bool(d148.get("AUTHENTIC_COMPILE_SATISFIED"))
    query_done = bool(d148.get("AUTHENTIC_QUERY_SATISFIED"))
    nodes = load_nodes(repo_root)
    changed: list[str] = []
    for node in nodes.values():
        if node.PACKAGE_ID not in AUTHENTIC_O2_PACKAGES:
            continue
        if node.status == "COMPLETED":
            continue
        target: str | None = None
        pkg = node.PACKAGE_ID
        if pkg == "AS-CODER-ALPHA-AUTHENTIC-INGEST-001" and not ingest_done:
            target = "READY"
        elif pkg == "AS-CODER-ALPHA-AUTHENTIC-COMPILE-001" and ingest_done and not compile_done:
            target = "READY"
        elif pkg == "AS-CODER-ALPHA-AUTHENTIC-QUERY-001" and compile_done and not query_done:
            target = "READY"
        if target and node.status != target:
            node.status = target
            node.DEPENDENCIES = []
            node.OWNER_GATE = "NONE"
            changed.append(node.NODE_ID)
    if changed:
        persist_nodes(repo_root, nodes)
    return changed
