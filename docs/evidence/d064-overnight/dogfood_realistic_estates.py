#!/usr/bin/env python3
"""D-049 / D-064 overnight dogfood: realistic controlled estates.

Label: REALISTIC_CONTROLLED_DOGFOOD (not authentic user estate).
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from project_atlas.estate_discovery import discover_estate

OUT_DIR = Path(__file__).resolve().parent
BASE = Path("/tmp/d064-estates")
RESULTS_PATH = OUT_DIR / "dogfood_realistic_estates_results.json"

ALPHA_UUID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
BETA_UUID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
GAMMA_UUID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git_project(
    root: Path,
    *,
    name: str | None = None,
    marker_id: str | None = None,
    marker_uuid: str | None = None,
    manifest: str = "pyproject",
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "README.md", f"# {root.name}\n")
    (root / ".git").mkdir(exist_ok=True)
    (root / "src").mkdir(exist_ok=True)
    if manifest == "pyproject":
        pkg = name or root.name
        _write(root / "pyproject.toml", f'[project]\nname = "{pkg}"\n')
    elif manifest == "package":
        pkg = name or root.name
        _write(root / "package.json", json.dumps({"name": pkg}) + "\n")
    if marker_id:
        uuid_line = f"project_uuid: {marker_uuid}\n" if marker_uuid else ""
        _write(
            root / ".atlas-project.yaml",
            f"project:\n  id: {marker_id}\n{uuid_line}",
        )


def _obsidian(root: Path) -> None:
    (root / ".obsidian").mkdir(parents=True, exist_ok=True)
    _write(root / ".obsidian" / "app.json", "{}\n")
    for n in ("a.md", "b.md", "c.md"):
        _write(root / n, "note\n")


def _knowledge_dir(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for n in ("one.md", "two.md", "three.md"):
        _write(root / n, "k\n")


def build_estate_a(base: Path) -> dict[str, Any]:
    """A: Estate/Alpha,Beta,Gamma — distinct git+manifest projects."""
    root = base / "A-distinct"
    if root.exists():
        shutil.rmtree(root)
    for name, uuid in (
        ("Alpha", ALPHA_UUID),
        ("Beta", BETA_UUID),
        ("Gamma", GAMMA_UUID),
    ):
        _git_project(
            root / name,
            name=name.lower(),
            marker_id=name.lower(),
            marker_uuid=uuid,
        )
    return {
        "estate_id": "A",
        "root": root,
        "description": "Distinct Alpha/Beta/Gamma git+manifest projects",
        "projects_expected": {"Alpha", "Beta", "Gamma"},
        "expected_min_projects": 3,
        "false_match_names": set(),
    }


def build_estate_b(base: Path) -> dict[str, Any]:
    """B: Monorepo with apps/, packages/, docs/, root .git.

    Honest ground truth: root is a project candidate (has .git); nested apps/
    packages may also score as projects if they have manifests+signals.
    """
    root = base / "B-monorepo"
    if root.exists():
        shutil.rmtree(root)
    (root / ".git").mkdir(parents=True)
    _write(root / "README.md", "# Monorepo\n")
    _write(root / "package.json", '{"name":"monorepo-root"}\n')
    (root / "docs").mkdir()
    _write(root / "docs" / "overview.md", "docs\n")

    for app in ("web", "api"):
        app_root = root / "apps" / app
        _write(app_root / "package.json", json.dumps({"name": app}) + "\n")
        _write(app_root / "README.md", f"# {app}\n")
        (app_root / "src").mkdir(parents=True)

    for pkg in ("ui", "shared"):
        pkg_root = root / "packages" / pkg
        _write(pkg_root / "package.json", json.dumps({"name": pkg}) + "\n")
        _write(pkg_root / "README.md", f"# {pkg}\n")
        (pkg_root / "src").mkdir(parents=True)

    # Honest expected: root + nested app/package candidates (may be 1–5).
    expected = {"B-monorepo", "web", "api", "ui", "shared"}
    return {
        "estate_id": "B",
        "root": root,
        "description": "Monorepo root.git + apps/ + packages/ + docs/",
        "projects_expected": expected,
        "expected_min_projects": 1,  # at least root
        "honest_note": (
            "Ground truth allows root+nested; count how many candidates "
            "surface honestly rather than force a single-root policy."
        ),
        "false_match_names": set(),
    }


def build_estate_c(base: Path) -> dict[str, Any]:
    """C: Active/Archive/Copies with copied markers (same UUID, different ids)."""
    root = base / "C-lifecycle"
    if root.exists():
        shutil.rmtree(root)
    shared_uuid = ALPHA_UUID
    _git_project(
        root / "Active" / "svc",
        name="svc",
        marker_id="svc",
        marker_uuid=shared_uuid,
    )
    _git_project(
        root / "Archive" / "svc-old",
        name="svc-old",
        marker_id="svc-old",
        marker_uuid=shared_uuid,
    )
    _git_project(
        root / "Copies" / "svc-copy",
        name="svc-copy",
        marker_id="svc",  # copied marker id
        marker_uuid=shared_uuid,
    )
    return {
        "estate_id": "C",
        "root": root,
        "description": "Active/Archive/Copies with copied markers",
        "projects_expected": {"svc", "svc-old", "svc-copy"},
        "expected_min_projects": 3,
        "false_match_names": set(),
    }


def build_estate_d(base: Path) -> dict[str, Any]:
    """D: ProjectA + ProjectB + ProjectA/node_modules/fake-project."""
    root = base / "D-node-modules"
    if root.exists():
        shutil.rmtree(root)
    for name in ("ProjectA", "ProjectB"):
        _git_project(root / name, name=name.lower(), manifest="package")
    fake = root / "ProjectA" / "node_modules" / "fake-project"
    _git_project(fake, name="fake-project", manifest="package")
    return {
        "estate_id": "D",
        "root": root,
        "description": "ProjectA/B with nested node_modules fake-project",
        "projects_expected": {"ProjectA", "ProjectB"},
        "expected_min_projects": 2,
        "false_match_names": {"fake-project"},
    }


def build_estate_e(base: Path) -> dict[str, Any]:
    """E: Repositories + Notes + Research + Obsidian."""
    root = base / "E-mixed"
    if root.exists():
        shutil.rmtree(root)
    _git_project(root / "Repositories" / "tooling", name="tooling")
    _git_project(root / "Repositories" / "platform", name="platform", manifest="package")
    _knowledge_dir(root / "Notes" / "inbox")
    # Notes itself may signal via nested knowledge_dir if we put notes under it —
    # also create a research tree and Obsidian vault at top level folders.
    _knowledge_dir(root / "Research" / "papers")
    # Ensure folder names match knowledge signals: put markdown clusters under
    # directories named notes/research, plus a true Obsidian vault.
    notes = root / "Notes"
    # Add enough .md at Notes level for markdown_cluster OR nest knowledge_dir
    for n in ("x.md", "y.md", "z.md"):
        _write(notes / n, "n\n")
    research = root / "Research"
    for n in ("r1.md", "r2.md", "r3.md"):
        _write(research / n, "r\n")
    _obsidian(root / "Obsidian" / "personal-vault")
    return {
        "estate_id": "E",
        "root": root,
        "description": "Repositories + Notes + Research + Obsidian",
        "projects_expected": {"tooling", "platform"},
        "expected_min_projects": 2,
        "false_match_names": set(),
        "expect_knowledge_min": 1,
        "expect_obsidian_min": 1,
    }


def _measure(spec: dict[str, Any]) -> dict[str, Any]:
    root: Path = spec["root"]
    expected: set[str] = set(spec["projects_expected"])
    false_names: set[str] = set(spec.get("false_match_names") or set())

    t0 = time.perf_counter()
    report = discover_estate(root)
    elapsed = time.perf_counter() - t0

    projects = report["candidates"]["projects"]
    knowledge = report["candidates"]["knowledge"]
    found_names = {Path(p["path"]).name for p in projects}
    found_paths = [p["path"] for p in projects]

    # Recall against expected basenames present in found set.
    hits = expected & found_names
    recall = (len(hits) / len(expected)) if expected else 1.0

    false_matches = sorted(found_names & false_names)
    # Also count unexpected names beyond expected as potential extras (honest).
    extras = sorted(found_names - expected - false_names)

    ambiguous = [
        p
        for p in projects
        if p.get("match_state") == "AMBIGUOUS" or p.get("required_review")
    ]
    obsidian = [k for k in knowledge if k.get("kind") == "obsidian_vault"]

    return {
        "estate_id": spec["estate_id"],
        "description": spec["description"],
        "root": str(root),
        "label": "REALISTIC_CONTROLLED_DOGFOOD",
        "PROJECTS_EXPECTED": sorted(expected),
        "PROJECTS_FOUND": sorted(found_names),
        "PROJECTS_FOUND_PATHS": found_paths,
        "PROJECTS_FOUND_COUNT": len(projects),
        "recall": round(recall, 4),
        "recall_hits": sorted(hits),
        "false_matches": false_matches,
        "false_match_count": len(false_matches),
        "extra_candidates_beyond_expected": extras,
        "ambiguous_or_review_projects": len(ambiguous),
        "ambiguous_match_states": sum(
            1 for p in projects if p.get("match_state") == "AMBIGUOUS"
        ),
        "time_seconds": round(elapsed, 6),
        "knowledge_count": len(knowledge),
        "obsidian_count": len(obsidian),
        "scan": report.get("scan"),
        "counts": report.get("counts"),
        "honest_note": spec.get("honest_note"),
        "pass_gates": {
            "min_projects": len(projects) >= int(spec.get("expected_min_projects", 0)),
            "no_false_matches": len(false_matches) == 0,
            "recall_complete": recall >= 1.0
            or spec["estate_id"] == "B",  # B measured honestly
            "knowledge_min": len(knowledge)
            >= int(spec.get("expect_knowledge_min", 0)),
            "obsidian_min": len(obsidian) >= int(spec.get("expect_obsidian_min", 0)),
        },
    }


def main() -> int:
    if BASE.exists():
        shutil.rmtree(BASE)
    BASE.mkdir(parents=True)

    specs = [
        build_estate_a(BASE),
        build_estate_b(BASE),
        build_estate_c(BASE),
        build_estate_d(BASE),
        build_estate_e(BASE),
    ]

    estate_results = [_measure(s) for s in specs]

    aggregate = {
        "estates": len(estate_results),
        "PROJECTS_EXPECTED_TOTAL": sum(
            len(r["PROJECTS_EXPECTED"]) for r in estate_results
        ),
        "PROJECTS_FOUND_TOTAL": sum(
            r["PROJECTS_FOUND_COUNT"] for r in estate_results
        ),
        "recall_mean": round(
            sum(r["recall"] for r in estate_results) / len(estate_results), 4
        ),
        "false_matches_total": sum(r["false_match_count"] for r in estate_results),
        "ambiguous_or_review_projects_total": sum(
            r["ambiguous_or_review_projects"] for r in estate_results
        ),
        "time_seconds_total": round(
            sum(r["time_seconds"] for r in estate_results), 6
        ),
        "knowledge_count_total": sum(r["knowledge_count"] for r in estate_results),
        "obsidian_count_total": sum(r["obsidian_count"] for r in estate_results),
        "all_gates_pass": all(
            all(v for v in r["pass_gates"].values()) for r in estate_results
        ),
    }

    results: dict[str, Any] = {
        "label": "REALISTIC_CONTROLLED_DOGFOOD",
        "authenticity": "NOT_AUTHENTIC_USER_ESTATE",
        "base": str(BASE),
        "estates": estate_results,
        "aggregate": aggregate,
        "honesty": {
            "DISCOVER_NE_INGEST": True,
            "DEMO_FIXTURE_NE_AUTHENTIC_PILOT": True,
            "label": "REALISTIC_CONTROLLED_DOGFOOD",
        },
    }

    RESULTS_PATH.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2, sort_keys=True))
    print(f"\nWrote {RESULTS_PATH}", flush=True)
    return 0 if aggregate["all_gates_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
