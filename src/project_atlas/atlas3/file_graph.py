"""AT3-011 — Isolated file / symbol graph.

Declared derived graph only. Does not walk host trees.
Graph != authority. Missing declarations stay UNKNOWN.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    OPS_RELATIVE,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
    require_project,
    require_vault,
)

PACKAGE_ID: Final[str] = "AT3-011"
DECLARED_NAME: Final[str] = "declared.json"


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "file-graph" / project_id / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error("FILE_GRAPH_CORRUPT", "declared file graph is not readable JSON") from exc
    if not isinstance(raw, dict):
        raise Atlas3Error("FILE_GRAPH_CORRUPT", "declared file graph must be an object")
    return raw


def _safe_relpath(value: str, *, field: str) -> str:
    text = value.strip().replace("\\", "/")
    unsafe = not text or text.startswith("/") or text == ".."
    if unsafe or text.startswith("../") or "/../" in text:
        raise Atlas3Error("UNSAFE_PATH", f"{field} path is not a safe relative path")
    return text


def _refs(raw: object, *, identity: str) -> list[str]:
    if not isinstance(raw, list):
        raise Atlas3Error("PROVENANCE_REQUIRED", f"{identity!r} requires evidence_refs")
    refs = [str(item).strip() for item in raw if str(item).strip()]
    if not refs:
        raise Atlas3Error("PROVENANCE_REQUIRED", f"{identity!r} requires evidence_refs")
    return refs


def _files(raw: object) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("FILE_GRAPH_CORRUPT", "files must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("FILE_GRAPH_CORRUPT", "files row is not an object")
        path = _safe_relpath(str(item.get("path") or item.get("id") or ""), field="file")
        evidence = item.get("evidence_refs") or item.get("evidence")
        rows.append(
            {
                "path": path,
                "kind": "file",
                "evidence_refs": _refs(evidence, identity=path),
                "authority": "derived",
            }
        )
    return rows


def _symbols(raw: object) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("FILE_GRAPH_CORRUPT", "symbols must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("FILE_GRAPH_CORRUPT", "symbols row is not an object")
        name = str(item.get("name") or item.get("id") or "").strip()
        if not name:
            raise Atlas3Error("FILE_GRAPH_IDENTITY_INCOMPLETE", "symbol row missing name")
        raw_path = str(item.get("file_path") or item.get("path") or "")
        file_path = _safe_relpath(raw_path, field="symbol")
        evidence = item.get("evidence_refs") or item.get("evidence")
        rows.append(
            {
                "name": name,
                "file_path": file_path,
                "kind": "symbol",
                "evidence_refs": _refs(evidence, identity=name),
                "authority": "derived",
            }
        )
    return rows


def compile_file_graph(vault: Path | str, project_id: str) -> dict[str, Any]:
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = _declared_path(root, pid)
    if not path.is_file():
        return {
            "package": PACKAGE_ID,
            "project_id": pid,
            "files": [],
            "symbols": [],
            "counts": {"files": 0, "symbols": 0},
            "status": "UNKNOWN",
            "reason": "NO_DECLARED_FILE_GRAPH",
            "walked_host_tree": False,
            "graph_is_authority": False,
            "promoted_to_truth_core": 0,
            "truth_boundary": TRUTH_BOUNDARY,
            "honesty": honesty_block(),
        }
    declared = _load_declared(path)
    declared_project = str(declared.get("project_id") or "").strip()
    if declared_project and declared_project != pid:
        raise Atlas3Error("CROSS_PROJECT", "declared file graph project_id does not match request")
    if declared.get("authentic_estate") is True or declared.get("authentic_pilot") is True:
        raise Atlas3Error(
            "FILE_GRAPH_AUTHORITY_CLAIMED",
            "declared file graph must not claim authentic estate",
        )
    files = _files(declared.get("files"))
    symbols = _symbols(declared.get("symbols"))
    return {
        "package": PACKAGE_ID,
        "project_id": pid,
        "files": files,
        "symbols": symbols,
        "counts": {"files": len(files), "symbols": len(symbols)},
        "status": "derived",
        "reason": "DECLARED_FILE_GRAPH",
        "walked_host_tree": False,
        "graph_is_authority": False,
        "promoted_to_truth_core": 0,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
