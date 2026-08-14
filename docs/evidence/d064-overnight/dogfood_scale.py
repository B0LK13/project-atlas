#!/usr/bin/env python3
"""D-049 / D-064 overnight dogfood: synthetic scale trees + truncation honesty."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from project_atlas.estate_discovery import discover_estate

OUT_DIR = Path(__file__).resolve().parent
BASE = Path("/tmp/d064-scale")
RESULTS_PATH = OUT_DIR / "dogfood_scale_results.json"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _count_dirs(root: Path) -> int:
    n = 0
    for p in root.rglob("*"):
        try:
            if p.is_dir() and not p.is_symlink():
                n += 1
        except OSError:
            continue
    return n


def _plant_real_project(root: Path, name: str) -> None:
    proj = root / name
    _write(proj / "README.md", f"# {name}\n")
    _write(proj / "package.json", json.dumps({"name": name}) + "\n")
    (proj / "src").mkdir(parents=True, exist_ok=True)
    (proj / ".git").mkdir(exist_ok=True)
    (proj / "docs").mkdir(exist_ok=True)
    _write(proj / "docs" / "readme.md", "docs\n")


def _plant_noise_tree(parent: Path, n_dirs: int, *, prefix: str) -> int:
    """Create ~n_dirs directories with heavy node_modules noise; return created count."""
    created = 0
    # Batch under buckets to stay within max_depth for discovery walk.
    bucket_size = 50
    buckets = max(1, (n_dirs + bucket_size - 1) // bucket_size)
    for b in range(buckets):
        bucket = parent / f"{prefix}-bucket-{b:04d}"
        bucket.mkdir(parents=True, exist_ok=True)
        created += 1
        # node_modules noise — discovery should ignore descending into these
        nm = bucket / "node_modules"
        nm.mkdir(exist_ok=True)
        created += 1
        for i in range(min(10, bucket_size // 5)):
            pkg = nm / f"pkg-{i:03d}"
            pkg.mkdir(exist_ok=True)
            created += 1
            _write(pkg / "package.json", '{"name":"noise"}\n')
            # Fake nested git that must remain ignored via node_modules policy.
            (pkg / ".git").mkdir(exist_ok=True)
            created += 1
        remaining = bucket_size - 1  # bucket itself counted
        # Fill with plain empty-ish dirs until target for this bucket.
        target_this = min(bucket_size, n_dirs - (created - (b * (bucket_size + 20))))
        # Simpler: keep adding filler dirs under bucket until we approach n_dirs.
        j = 0
        while created < n_dirs and j < bucket_size * 2:
            d = bucket / f"filler-{j:04d}"
            d.mkdir(exist_ok=True)
            created += 1
            j += 1
            if created >= n_dirs:
                break
        if created >= n_dirs:
            break
    # If still short, add linear fillers at parent.
    k = 0
    while created < n_dirs:
        d = parent / f"{prefix}-extra-{k:05d}"
        d.mkdir(exist_ok=True)
        created += 1
        k += 1
    return created


def build_scale_tree(root: Path, target_dirs: int, *, real_projects: int) -> dict[str, Any]:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    projects_dir = root / "projects"
    projects_dir.mkdir()
    for i in range(real_projects):
        _plant_real_project(projects_dir, f"real-proj-{i:03d}")

    noise_root = root / "noise"
    noise_root.mkdir()
    # Approximate: count after project planting, then fill to target.
    current = _count_dirs(root)
    need = max(0, target_dirs - current)
    if need:
        _plant_noise_tree(noise_root, need, prefix="n")

    total = _count_dirs(root)
    return {
        "root": root,
        "target_dirs": target_dirs,
        "TOTAL_DIRECTORIES": total,
        "planted_real_projects": real_projects,
    }


def _scan(label: str, meta: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    root: Path = meta["root"]
    t0 = time.perf_counter()
    report = discover_estate(root, **kwargs)
    elapsed = time.perf_counter() - t0
    scan = report.get("scan") or {}
    return {
        "label": label,
        "root": str(root),
        "TOTAL_DIRECTORIES": meta["TOTAL_DIRECTORIES"],
        "target_dirs": meta["target_dirs"],
        "planted_real_projects": meta["planted_real_projects"],
        "PROJECT_CANDIDATES": report["counts"]["projects"],
        "KNOWLEDGE_CANDIDATES": report["counts"]["knowledge"],
        "SCAN_SECONDS": round(elapsed, 6),
        "SCAN_COMPLETE": scan.get("scan_complete"),
        "TRUNCATION": {
            "truncation_reason": scan.get("truncation_reason"),
            "project_limit_reached": scan.get("project_limit_reached"),
            "knowledge_limit_reached": scan.get("knowledge_limit_reached"),
            "max_project_candidates": scan.get("max_project_candidates"),
            "dirs_visited": scan.get("dirs_visited"),
        },
        "project_names": sorted(
            Path(p["path"]).name for p in report["candidates"]["projects"]
        ),
        "false_node_modules_projects": [
            p["path"]
            for p in report["candidates"]["projects"]
            if "node_modules" in p["path"]
        ],
    }


def main() -> int:
    if BASE.exists():
        shutil.rmtree(BASE)
    BASE.mkdir(parents=True)

    sizes = [
        ("SMALL", 100, 3),
        ("MEDIUM", 1000, 8),
        ("LARGE", 5000, 15),
    ]

    scale_rows: list[dict[str, Any]] = []
    for label, target, n_proj in sizes:
        meta = build_scale_tree(BASE / label.lower(), target, real_projects=n_proj)
        # Allow deeper walk for large synthetic trees (noise is under /noise/buckets).
        max_depth = 10 if label == "LARGE" else 8
        row = _scan(label, meta, max_depth=max_depth, include_knowledge=False)
        scale_rows.append(row)

    # Truncation honesty: force max_project_candidates=5 on a tree with >5 projects.
    trunc_root = BASE / "truncation"
    if trunc_root.exists():
        shutil.rmtree(trunc_root)
    trunc_root.mkdir()
    for i in range(12):
        _plant_real_project(trunc_root, f"trunc-proj-{i:02d}")
    trunc_meta = {
        "root": trunc_root,
        "target_dirs": _count_dirs(trunc_root),
        "TOTAL_DIRECTORIES": _count_dirs(trunc_root),
        "planted_real_projects": 12,
    }
    trunc_row = _scan(
        "TRUNCATION_MAX5",
        trunc_meta,
        include_knowledge=False,
        max_project_candidates=5,
    )
    trunc_ok = (
        trunc_row["PROJECT_CANDIDATES"] == 5
        and trunc_row["SCAN_COMPLETE"] is False
        and trunc_row["TRUNCATION"]["project_limit_reached"] is True
        and trunc_row["TRUNCATION"]["truncation_reason"] == "project_limit_reached"
    )

    results: dict[str, Any] = {
        "label": "D064_OVERNIGHT_SCALE_DOGFOOD",
        "authenticity": "SYNTHETIC_SCALE_TREES",
        "base": str(BASE),
        "sizes": scale_rows,
        "truncation_honesty": {
            **trunc_row,
            "pass": trunc_ok,
            "expect": {
                "max_project_candidates": 5,
                "PROJECT_CANDIDATES": 5,
                "SCAN_COMPLETE": False,
                "truncation_reason": "project_limit_reached",
            },
        },
        "aggregate": {
            "no_node_modules_project_candidates": all(
                not r["false_node_modules_projects"] for r in scale_rows
            ),
            "all_scans_recorded": all(
                r["SCAN_SECONDS"] is not None for r in scale_rows
            ),
            "truncation_honesty_pass": trunc_ok,
        },
        "honesty": {
            "SYNTHETIC_NE_AUTHENTIC": True,
            "TRUNCATION_MUST_BE_EXPLICIT": trunc_ok,
        },
    }

    RESULTS_PATH.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2, sort_keys=True))
    print(f"\nWrote {RESULTS_PATH}", flush=True)
    return 0 if trunc_ok and results["aggregate"]["no_node_modules_project_candidates"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
