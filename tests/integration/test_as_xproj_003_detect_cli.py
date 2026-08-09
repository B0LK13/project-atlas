"""AS-XPROJ-003 — thin CLI smoke for detect-project-duplicates."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.cli import main

PID_A = "11111111-1111-4111-8111-111111111111"
PID_B = "22222222-2222-4222-8222-222222222222"


def test_detect_project_duplicates_cli_write(tmp_path: Path, monkeypatch: object) -> None:
    projects = tmp_path / "projects.json"
    projects.write_text(
        json.dumps(
            {
                "projects": [
                    {
                        "project_id": PID_A,
                        "canonical_remote_url": "https://example.com/dup.git",
                        "evidence_refs": [
                            {"relative_path": "sources/a.md", "sha256": "a" * 64}
                        ],
                    },
                    {
                        "project_id": PID_B,
                        "canonical_remote_url": "https://example.com/dup",
                        "evidence_refs": [
                            {"relative_path": "sources/b.md", "sha256": "b" * 64}
                        ],
                    },
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "sys.argv",
        [
            "atlas",
            "detect-project-duplicates",
            "--projects",
            str(projects),
            "--vault",
            str(vault),
            "--write",
        ],
    )
    assert main() == 0
    out_dir = vault / "generated" / "xproj" / "duplicate-candidates"
    assert out_dir.is_dir()
    assert list(out_dir.glob("*.json"))
