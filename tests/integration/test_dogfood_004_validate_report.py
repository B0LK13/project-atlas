"""DOGFOOD-004 — `atlas validate-report` (additive aggregate diagnostics).

Authentic first-run dogfooding found that `atlas validate`'s underlying
`project_atlas.validation.validate()` already computes every finding (every
broken link, freshness/orphan/portfolio/knowledge-state issue) into
``result["errors"]`` and ``result["findings"]`` before deciding pass/fail --
it is not fail-fast at the library level. The gap is in `cli.py`'s existing
`validate` command: on a blocking failure it logs the errors, then returns
immediately (`cli.py`'s ``if exit_code != EXIT_OK: ... return EXIT_ERROR``),
never reaching the warning/info-printing loop below it. So the moment any
error exists, every accompanying warning/info finding the library already
computed is silently dropped from the operator's view.

`ingestion.py`/`cli.py`'s *existing* command bodies are frozen while
`FULL_LIVE_DEMO_READY = NO` (`docs/atlas-3/ARCHITECTURE.md` SS9,
`tests/unit/test_atlas3_demo_isolation_001.py`), so the fix here is a
brand-new, additive `atlas validate-report` command registered entirely
inside `atlas3/cli.py` (an explicitly unfrozen namespace) via the existing,
already-generic `register_atlas3_parsers`/`dispatch_atlas3` hooks in
`cli.py` -- `atlas validate`'s own behavior and exit code are untouched.

Required property: AGGREGATE_REPORTING != IGNORE_ERRORS -- the new command
must still exit 1 on any error, exactly like `atlas validate`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_ERROR, EXIT_OK, main

pytestmark = pytest.mark.integration


def _fixture(root: Path) -> Path:
    source = root / "source"
    (source / "docs").mkdir(parents=True)
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: fixture-d004\n", encoding="utf-8"
    )
    (source / "README.md").write_text("# Fixture D004\n\nOverview.\n", encoding="utf-8")
    (source / "docs" / "ARCHITECTURE.md").write_text(
        "# Architecture\n\nSystem design.\n", encoding="utf-8"
    )
    return source


def _build_vault(source: Path, vault: Path, tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest),
                "--vault",
                str(vault),
                "--source",
                str(source),
            ]
        )
        == EXIT_OK
    )
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK


def test_clean_vault_ok_matches_validate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _fixture(tmp_path)
    vault = tmp_path / "vault"
    _build_vault(source, vault, tmp_path)

    capsys.readouterr()
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    capsys.readouterr()
    assert main(["validate-report", "--vault", str(vault)]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["errors"] == []


def test_broken_link_exit_code_matches_validate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _fixture(tmp_path)
    vault = tmp_path / "vault"
    _build_vault(source, vault, tmp_path)

    claims = vault / "projects" / "fixture-d004" / "claims.md"
    claims.write_text(
        claims.read_text(encoding="utf-8") + "\n[Broken](does-not-exist.md)\n",
        encoding="utf-8",
    )

    capsys.readouterr()
    assert main(["validate", "--vault", str(vault)]) == EXIT_ERROR

    capsys.readouterr()
    assert main(["validate-report", "--vault", str(vault)]) == EXIT_ERROR
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert any("broken link" in error for error in payload["errors"])
    # The full underlying result (not a filtered subset) is what the plain
    # `validate` command computes internally but only partially surfaces.
    assert "findings" in payload
    assert "markdown_files" in payload


def test_validate_report_exit_code_uses_canonical_severity_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`validate-report` must derive its exit code the same way `atlas
    validate` does -- via `validation_exit_code()`'s AS-H-010 severity
    matrix -- not by re-deriving it from `result["ok"]` directly. In the
    real `validate()` output these currently always agree (every
    Severity.ERROR finding is paired with an `errors` entry), so this test
    forces the divergent case: an ERROR-severity finding with an empty
    legacy `errors` list and `ok: True`. `validation_exit_code()` must
    still report failure, and `validate-report` must exit non-zero."""
    source = _fixture(tmp_path)
    vault = tmp_path / "vault"
    _build_vault(source, vault, tmp_path)

    from project_atlas.domain import Severity

    def _fake_validate(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "ok": True,
            "errors": [],
            "findings": [
                {
                    "finding_id": "err.1",
                    "rule_id": "synthetic-error",
                    "severity": Severity.ERROR.value,
                    "gate": "structural",
                    "message": "synthetic error finding not mirrored in errors[]",
                    "path": None,
                    "concept_id": None,
                }
            ],
            "markdown_files": 1,
        }

    monkeypatch.setattr("project_atlas.atlas3.cli._run_validate", _fake_validate)

    capsys.readouterr()
    code = main(["validate-report", "--vault", str(vault)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True  # the raw (synthetic) result really does say ok=True
    assert code == EXIT_ERROR  # but the canonical severity mapping still fails closed


def test_validate_report_does_not_change_existing_validate_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Additive means additive: adding validate-report changes nothing about
    what `atlas validate` itself prints or returns."""
    source = _fixture(tmp_path)
    vault = tmp_path / "vault"
    _build_vault(source, vault, tmp_path)

    capsys.readouterr()
    code = main(["validate", "--vault", str(vault)])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert out.startswith("validated ") and "Markdown files" in out
