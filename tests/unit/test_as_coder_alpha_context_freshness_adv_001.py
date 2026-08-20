"""AS-CODER-ALPHA-CONTEXT-FRESHNESS-ADV-001 — frozen estate vs later live estate.

Does not retarget #378. Does not duplicate owner-held #419 banners/CLI.
Reuses inventory_drift. No second source-hash engine.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.agent_handoff import (
    FROZEN_ESTATE_NOT_CURRENT,
    PACKAGE_FRESHNESS_ADV,
    bind_estate_at_write,
    create_handoff,
    evaluate_estate_currentness,
    evaluate_written_context,
    export_agent_context,
    resume_handoff,
)
from project_atlas.connect import connect_project
from project_atlas.inventory_drift import PACKAGE_ID as DRIFT_PACKAGE
from project_atlas.source_identity import canonical_source_sha256


def _write_manifest(vault: Path, root: Path, sources: list[dict[str, object]]) -> None:
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"source_root": str(root), "sources": sources},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _seed_project(vault: Path, project_id: str) -> None:
    note = vault / "projects" / project_id / "project.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    semantic = {
        "project_id": project_id,
        "lifecycle": "active",
        "sources": [],
        "coverage": [],
    }
    note.write_text(
        "---\ntype: Project\ntitle: "
        + project_id
        + "\n---\n\n# "
        + project_id
        + "\n\n<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps(semantic)
        + "\n```\n",
        encoding="utf-8",
    )


def _pair(
    tmp_path: Path,
    *,
    drift: bool = False,
    project_id: str = "harbor",
    extra_manifest_field: str | None = None,
) -> tuple[Path, Path]:
    root = tmp_path / "src"
    root.mkdir(exist_ok=True)
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text("# Harbor\n\nstable\n", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    _seed_project(vault, project_id)
    payload: dict[str, object] = {
        "source_root": str(root),
        "sources": [
            {
                "path": "README.md",
                "sha256": canonical_source_sha256(readme),
                "likely_project": project_id,
            }
        ],
    }
    if extra_manifest_field is not None:
        payload["reconnect_generation"] = extra_manifest_field
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if drift:
        readme.write_text("# Harbor\n\ndrifted\n", encoding="utf-8")
    return vault, root


def _layer_b_snapshot(vault: Path) -> dict[str, str]:
    root = vault / "projects"
    if not root.is_dir():
        return {}
    return {
        path.relative_to(vault).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_case_a_context_written_fresh_then_source_changes(tmp_path: Path) -> None:
    vault, root = _pair(tmp_path, drift=False)
    before = _layer_b_snapshot(vault)
    ctx = export_agent_context(vault, "harbor", refresh_brief=False)
    assert ctx["freshness"]["status"] == "FRESH"
    assert ctx["freshness"]["is_current"] is True
    assert ctx["estate_binding"]["package"] == PACKAGE_FRESHNESS_ADV
    (root / "README.md").write_text("# Harbor\n\nchanged-later\n", encoding="utf-8")
    later = evaluate_written_context(vault, "harbor")
    assert later["status"] == "STALE"
    assert later["is_current"] is False
    assert later["honesty"]["stale_is_current"] is False
    assert later["honesty"]["fresh_is_authority"] is False
    assert "README.md" in later["changed_paths"]
    assert _layer_b_snapshot(vault) == before


def test_case_b_handoff_written_fresh_then_source_changes(tmp_path: Path) -> None:
    project = tmp_path / "handoff-adv"
    project.mkdir()
    (project / "README.md").write_text("# Freshness Adv\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\nKeep honest.\n",
        encoding="utf-8",
    )
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    created = create_handoff(vault, project_id, note="adv-fresh", refresh_brief=False)
    assert (created.get("freshness") or {}).get("status") in {"FRESH", "UNKNOWN"}
    (project / "README.md").write_text("# Freshness Adv\n\nv2 changed\n", encoding="utf-8")
    resumed = resume_handoff(vault, handoff_id=created["handoff_id"])
    assert resumed["status"] == "resumed"
    assert resumed["freshness"]["status"] == "STALE"
    assert resumed["freshness"]["is_current"] is False
    assert resumed["honesty"]["stale_is_current"] is False
    assert resumed["honesty"]["handoff_is_authority"] is False
    assert resumed["estate_binding_at_write"]["manifest_sha256"]


def test_case_c_written_unknown_does_not_become_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_project(vault, "harbor")
    ctx = export_agent_context(vault, "harbor", refresh_brief=False)
    assert ctx["freshness"]["status"] == "UNKNOWN"
    assert ctx["honesty"]["unknown_is_fresh"] is False
    assert ctx["honesty"]["unknown_is_current"] is False
    root = tmp_path / "src"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("# Harbor\n\nstable\n", encoding="utf-8")
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
    later = evaluate_written_context(vault, "harbor")
    assert later["status"] == "UNKNOWN"
    assert later["is_current"] is False
    assert later["honesty"]["unknown_is_fresh"] is False
    assert later["reason_code"] == "WRITTEN_UNKNOWN_NOT_FRESH"


def test_case_d_written_stale_does_not_default_current_after_reconnect(
    tmp_path: Path,
) -> None:
    vault, _root = _pair(tmp_path, drift=True)
    ctx = export_agent_context(vault, "harbor", refresh_brief=False)
    assert ctx["freshness"]["status"] == "STALE"
    assert ctx["honesty"]["stale_is_current"] is False
    # Reconnect refreshes the manifest to the drifted bytes.
    _pair(tmp_path, drift=False, extra_manifest_field="reconnect-after-stale")
    later = evaluate_written_context(vault, "harbor")
    assert later["status"] == "STALE"
    assert later["is_current"] is False
    assert later["honesty"]["stale_is_current"] is False
    assert later["estate_compare"]["source_digests_changed"] is True or (
        later["estate_compare"]["manifest_identity_changed"] is True
    )


def test_case_e_reconnect_keeps_old_pack_distinguishable(tmp_path: Path) -> None:
    vault, _root = _pair(tmp_path, drift=False)
    old = export_agent_context(vault, "harbor", refresh_brief=False)
    old_binding = old["estate_binding"]
    assert old["freshness"]["is_current"] is True
    old_sha = old_binding["manifest_sha256"]
    # Reconnect rewrites the manifest with the same source hashes.
    _pair(tmp_path, drift=False, extra_manifest_field="reconnect-2")
    later = evaluate_written_context(vault, "harbor")
    assert later["source_drift"]["status"] == "FRESH"
    assert later["status"] == "STALE"
    assert later["is_current"] is False
    assert later["reason_code"] == "FROZEN_ESTATE_NOT_CURRENT"
    assert FROZEN_ESTATE_NOT_CURRENT in later["notes"]
    assert later["estate_compare"]["manifest_identity_changed"] is True
    assert later["estate_compare"]["frozen_manifest_sha256"] == old_sha
    new = export_agent_context(vault, "harbor", refresh_brief=False)
    assert new["estate_binding"]["manifest_sha256"] != old_sha
    assert new["freshness"]["is_current"] is True
    assert new["estate_binding"]["manifest_sha256"] != old_binding["manifest_sha256"]


def test_case_f_identical_content_restore_does_not_invent_history(
    tmp_path: Path,
) -> None:
    vault, root = _pair(tmp_path, drift=False)
    export_agent_context(vault, "harbor", refresh_brief=False)
    original = (root / "README.md").read_text(encoding="utf-8")
    (root / "README.md").write_text("# Harbor\n\nmid-change\n", encoding="utf-8")
    mid = evaluate_written_context(vault, "harbor")
    assert mid["status"] == "STALE"
    (root / "README.md").write_text(original, encoding="utf-8")
    restored = evaluate_written_context(vault, "harbor")
    assert restored["status"] == "FRESH"
    assert restored["is_current"] is True
    assert restored["estate_compare"]["manifest_identity_changed"] is False
    assert restored["estate_compare"]["source_digests_changed"] is False
    assert restored["honesty"]["invented_facts"] is False


def test_sibling_project_rows_do_not_leak(tmp_path: Path) -> None:
    vault, _ = _pair(tmp_path, drift=False, project_id="harbor-portal")
    report = evaluate_estate_currentness(vault, "harbor")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_healthy"] is False
    assert report["changed_paths"] == []


def test_no_secret_echo_or_layer_b_writes(tmp_path: Path) -> None:
    vault, _root = _pair(tmp_path, drift=True)
    before = _layer_b_snapshot(vault)
    ctx = export_agent_context(vault, "harbor", refresh_brief=False)
    secret = "# Harbor\n\ndrifted\n"
    payload = json.loads((vault / ctx["json_path"]).read_text(encoding="utf-8"))
    text = (vault / ctx["markdown_path"]).read_text(encoding="utf-8")
    assert secret not in text
    assert secret not in json.dumps(payload)
    assert _layer_b_snapshot(vault) == before


def test_no_second_drift_engine() -> None:
    root = Path(__file__).resolve().parents[2]
    handoff = (root / "src/project_atlas/agent_handoff.py").read_text(encoding="utf-8")
    assert "from project_atlas.inventory_drift import" in handoff
    assert "attach_source_drift" in handoff
    assert "def evaluate_connect_inventory_drift" not in handoff
    assert "canonical_source_sha256" not in handoff
    assert "context_freshness_adv.py" not in handoff
    assert "sha256_file" not in handoff
    assert PACKAGE_FRESHNESS_ADV
    assert DRIFT_PACKAGE == "AS-CODER-ALPHA-INVENTORY-DRIFT-001"


def test_bind_estate_is_not_authority(tmp_path: Path) -> None:
    vault, _ = _pair(tmp_path, drift=False)
    binding = bind_estate_at_write(vault, "harbor")
    assert binding["authority"] is False
    assert binding["honesty"]["frozen_binding_is_authority"] is False
    assert binding["honesty"]["fresh_is_authority"] is False
    assert binding["engine"] == DRIFT_PACKAGE
