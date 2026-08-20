"""AS-CODER-ALPHA-INVENTORY-DRIFT-001 — shared connect-inventory freshness."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.inventory_drift import (
    PACKAGE_ID,
    evaluate_connect_inventory_drift,
)
from project_atlas.overview import build_overview_lens
from project_atlas.project_architecture import build_architecture_lens
from project_atlas.source_identity import canonical_source_sha256


def _write_manifest(
    vault: Path,
    root: Path,
    sources: list[dict[str, object]],
) -> None:
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "source_root": str(root),
                "sources": sources,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _seed_overview(vault: Path, project_id: str) -> None:
    note = vault / "projects" / project_id / "project.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\ntype: Project\ntitle: harbor\n---\n\n# harbor\n\n"
        "<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps({"project_id": project_id, "sources": [], "coverage": []})
        + "\n```\n",
        encoding="utf-8",
    )
    imported = vault / "sources" / "imported-documents"
    imported.mkdir(parents=True)
    (imported / "source-readme.md").write_text(
        "# Harbor\n\nPersistent brain fixture.\n",
        encoding="utf-8",
    )
    semantic = {
        "project_id": project_id,
        "sources": [{"path": "README.md", "source_id": "source-readme"}],
        "coverage": [],
    }
    note.write_text(
        "---\ntype: Project\ntitle: harbor\n---\n\n# harbor\n\n"
        "<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps(semantic)
        + "\n```\n",
        encoding="utf-8",
    )


def test_unchanged_source_is_fresh(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("# Harbor\n\nstable\n", encoding="utf-8")
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "README.md",
                "sha256": canonical_source_sha256(readme),
                "likely_project": "harbor",
            }
        ],
    )
    drift = evaluate_connect_inventory_drift(vault, "harbor")
    assert drift["status"] == "FRESH"
    assert drift["honesty"]["unknown_is_fresh"] is False
    assert drift["package"] == PACKAGE_ID


def test_modified_and_deleted_sources_are_stale(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    keep = root / "README.md"
    keep.write_text("# Harbor\n\nv1\n", encoding="utf-8")
    gone = root / "docs"
    gone.mkdir()
    plan = gone / "plan.md"
    plan.write_text("# Plan\n\nv1\n", encoding="utf-8")
    digest_keep = canonical_source_sha256(keep)
    digest_plan = canonical_source_sha256(plan)
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "README.md",
                "sha256": digest_keep,
                "likely_project": "harbor",
            },
            {
                "path": "docs/plan.md",
                "sha256": digest_plan,
                "likely_project": "harbor",
            },
        ],
    )
    keep.write_text("# Harbor\n\nv2\n", encoding="utf-8")
    plan.unlink()
    drift = evaluate_connect_inventory_drift(vault, "harbor")
    assert drift["status"] == "STALE"
    assert drift["honesty"]["stale_is_current"] is False
    assert "README.md" in drift["changed_paths"]
    assert "docs/plan.md" in drift["changed_paths"]


def test_missing_root_and_manifest_are_unknown_not_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    absent = evaluate_connect_inventory_drift(vault, "harbor")
    assert absent["status"] == "UNKNOWN"
    assert absent["reason_code"] == "MANIFEST_ABSENT"
    assert absent["honesty"]["unknown_is_fresh"] is False
    assert absent["honesty"]["unknown_is_healthy"] is False

    _write_manifest(
        vault,
        tmp_path / "missing-root",
        [
            {
                "path": "README.md",
                "sha256": "abc",
                "likely_project": "harbor",
            }
        ],
    )
    unverified = evaluate_connect_inventory_drift(vault, "harbor")
    assert unverified["status"] == "UNKNOWN"
    assert unverified["reason_code"] == "SOURCE_ROOT_UNVERIFIED"


def test_excluded_and_sibling_and_unscoped_rows_do_not_leak(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("# Harbor\n\nstable\n", encoding="utf-8")
    sibling = root / "other.md"
    sibling.write_text("# Other\n\nchanged\n", encoding="utf-8")
    excluded = root / "secrets.env"
    excluded.write_text("AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
    vault = tmp_path / "vault"
    digest = canonical_source_sha256(readme)
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "README.md",
                "sha256": digest,
                "likely_project": "harbor",
            },
            {
                "path": "other.md",
                "sha256": "deadbeef",
                "likely_project": "sibling",
            },
            {
                "path": "secrets.env",
                "sha256": "cafebabe",
                "exclusion_reason": "sensitive-metadata-only",
            },
            {
                "path": "unowned.md",
                "sha256": "00",
            },
        ],
    )
    sibling.write_text("# Other\n\ndrift\n", encoding="utf-8")
    excluded.write_text("AKIAIOSFODNN7EXAMPLE-rotated\n", encoding="utf-8")
    drift = evaluate_connect_inventory_drift(vault, "harbor")
    assert drift["status"] == "FRESH"
    payload = json.dumps(drift)
    assert "AKIAIOSFODNN7EXAMPLE" not in payload
    assert "other.md" not in drift["changed_paths"]
    assert "unowned.md" not in drift["changed_paths"]


def test_path_escape_is_rejected_as_stale_not_followed(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret-outside\n", encoding="utf-8")
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "../outside.txt",
                "sha256": "00",
                "likely_project": "harbor",
            }
        ],
    )
    drift = evaluate_connect_inventory_drift(vault, "harbor")
    assert drift["status"] == "STALE"
    payload = json.dumps(drift)
    assert "secret-outside" not in payload


def test_unicode_path_and_deterministic_output(tmp_path: Path) -> None:
    root = tmp_path / "src"
    docs = root / "docs"
    docs.mkdir(parents=True)
    note = docs / "café.md"
    note.write_text("# Café\n\nstable\n", encoding="utf-8")
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "docs/café.md",
                "sha256": canonical_source_sha256(note),
                "likely_project": "harbor",
            }
        ],
    )
    first = evaluate_connect_inventory_drift(vault, "harbor")
    second = evaluate_connect_inventory_drift(vault, "harbor")
    assert first == second
    assert first["status"] == "FRESH"


def test_architecture_path_filter_ignores_readme_churn(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    readme = root / "README.md"
    plan = root / "docs"
    plan.mkdir()
    plan_md = plan / "plan.md"
    readme.write_text("# Harbor\n\nv1\n", encoding="utf-8")
    plan_md.write_text("# Plan\n\nv1\n", encoding="utf-8")
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "README.md",
                "sha256": canonical_source_sha256(readme),
                "likely_project": "harbor",
            },
            {
                "path": "docs/plan.md",
                "sha256": canonical_source_sha256(plan_md),
                "likely_project": "harbor",
            },
        ],
    )
    readme.write_text("# Harbor\n\nv2\n", encoding="utf-8")
    from project_atlas.project_architecture import _architecture_rank

    drift = evaluate_connect_inventory_drift(
        vault,
        "harbor",
        path_filter=lambda path: _architecture_rank(path) is not None,
    )
    assert drift["status"] == "FRESH"


def test_overview_lens_attaches_stale_without_echoing_secrets(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("# Harbor\n\nv1\n", encoding="utf-8")
    vault = tmp_path / "vault"
    _seed_overview(vault, "harbor")
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "README.md",
                "sha256": canonical_source_sha256(readme),
                "likely_project": "harbor",
            }
        ],
    )
    readme.write_text("# Harbor\n\nAKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
    lens = build_overview_lens(vault, "harbor")
    assert lens["source_drift"]["status"] == "STALE"
    assert lens["honesty"]["stale_is_current"] is False
    assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(lens)
    assert lens["status"] in {"derived", "unknown"}


def test_architecture_lens_attaches_unknown_when_manifest_missing(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    lens = build_architecture_lens(vault, "harbor")
    assert lens["source_drift"]["status"] == "UNKNOWN"
    assert lens["honesty"]["unknown_is_healthy"] is False
    assert lens["honesty"]["unknown_is_fresh"] is False


def test_unknown_project_sentinel_never_owns_scoped_inventory(tmp_path: Path) -> None:
    """D-OWNER-DRIFT-039: unknown-project is never an authoritative owner."""
    root = tmp_path / "src"
    root.mkdir()
    harbor = root / "harbor.md"
    harbor.write_text("# Harbor\n\nowned\n", encoding="utf-8")
    unowned = root / "unowned.md"
    unowned.write_text("# Unowned\n\nchanged\n", encoding="utf-8")
    empty_owner = root / "empty.md"
    empty_owner.write_text("# Empty\n\nchanged\n", encoding="utf-8")
    sentinel_likely = root / "sentinel-likely.md"
    sentinel_likely.write_text("# Sentinel likely\n\nchanged\n", encoding="utf-8")
    sentinel_pid = root / "sentinel-pid.md"
    sentinel_pid.write_text("# Sentinel pid\n\nchanged\n", encoding="utf-8")
    sibling = root / "sibling.md"
    sibling.write_text("# Sibling\n\nchanged\n", encoding="utf-8")
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "harbor.md",
                "sha256": canonical_source_sha256(harbor),
                "likely_project": "harbor",
            },
            {
                "path": "unowned.md",
                "sha256": "00",
            },
            {
                "path": "empty.md",
                "sha256": "00",
                "likely_project": "   ",
            },
            {
                "path": "sentinel-likely.md",
                "sha256": "00",
                "likely_project": "unknown-project",
            },
            {
                "path": "sentinel-pid.md",
                "sha256": "00",
                "project_id": "unknown-project",
            },
            {
                "path": "sibling.md",
                "sha256": "00",
                "likely_project": "portal",
            },
        ],
    )
    for path in (unowned, empty_owner, sentinel_likely, sentinel_pid, sibling):
        path.write_text(path.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")

    harbor_drift = evaluate_connect_inventory_drift(vault, "harbor")
    assert harbor_drift["status"] == "FRESH"
    leaked = set(harbor_drift["changed_paths"])
    assert "unowned.md" not in leaked
    assert "empty.md" not in leaked
    assert "sentinel-likely.md" not in leaked
    assert "sentinel-pid.md" not in leaked
    assert "sibling.md" not in leaked

    sentinel_scope = evaluate_connect_inventory_drift(vault, "unknown-project")
    assert sentinel_scope["status"] == "UNKNOWN"
    assert sentinel_scope["reason_code"] == "NO_ACTIVE_SOURCES"
    assert sentinel_scope["changed_paths"] == []


def test_absolute_and_symlink_escape_rejected_without_echo(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    outside = tmp_path / "secret-outside.txt"
    outside.write_text("SECRET-OUTSIDE-CONTENT\n", encoding="utf-8")
    escape = root / "escape.md"
    escape.symlink_to(outside)
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "/etc/passwd",
                "sha256": "00",
                "likely_project": "harbor",
            },
            {
                "path": "C:/Windows/system32/config",
                "sha256": "00",
                "likely_project": "harbor",
            },
            {
                "path": "escape.md",
                "sha256": "00",
                "likely_project": "harbor",
            },
        ],
    )
    drift = evaluate_connect_inventory_drift(vault, "harbor")
    assert drift["status"] == "STALE"
    payload = json.dumps(drift)
    assert "SECRET-OUTSIDE-CONTENT" not in payload
    assert "/etc/passwd" in drift["changed_paths"]
    assert "escape.md" in drift["changed_paths"]
