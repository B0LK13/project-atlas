"""PROD-DOCTOR-001 -- `atlas doctor` environment / Vault self-diagnosis.

Verifies objective, deterministic, read-only health checks and the CLI
exit-code contract (0 unless an ERROR check is present). Reinforces the
project invariants: objective signals only, and unknown != healthy.
"""

from __future__ import annotations

import json

import pytest

from project_atlas.cli import main
from project_atlas.config import AtlasConfig
from project_atlas.doctor import (
    Check,
    DoctorReport,
    render_text,
    run_doctor,
    to_dict,
)
from project_atlas.scaffold import create_scaffold


def test_rollup_precedence_error_over_warn_over_unknown_over_ok() -> None:
    report = DoctorReport(
        checks=(
            Check("a", "ok", ""),
            Check("b", "unknown", ""),
            Check("c", "warn", ""),
            Check("d", "error", ""),
        )
    )
    assert report.rollup == "error"
    assert report.ok is False


def test_rollup_unknown_is_not_healthy_but_not_fatal() -> None:
    report = DoctorReport(checks=(Check("a", "ok", ""), Check("b", "unknown", "")))
    # unknown != healthy: it dominates ok in the rollup...
    assert report.rollup == "unknown"
    # ...but is non-fatal (no ERROR), so the command still exits 0.
    assert report.ok is True


def test_environment_checks_pass_without_vault() -> None:
    report = run_doctor(AtlasConfig())
    names = {check.name for check in report.checks}
    assert "python-runtime" in names
    assert "atlas-package" in names
    assert "package-data:schemas" in names
    assert "dependency:pydantic" in names
    assert "dependency:jsonschema" in names
    # No ERROR checks in a correctly installed environment.
    assert report.ok is True
    assert report.rollup in {"ok", "warn", "unknown"}
    # Without --vault, no vault checks are emitted.
    assert not any(name.startswith("vault:") for name in names)


def test_absent_vault_is_unknown_not_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    missing = tmp_path / "does-not-exist"
    report = run_doctor(AtlasConfig(), missing)
    vault_present = next(c for c in report.checks if c.name == "vault:present")
    assert vault_present.status == "unknown"
    # Unknown is non-fatal.
    assert report.ok is True


def test_scaffolded_vault_reports_present_and_ok(tmp_path) -> None:  # type: ignore[no-untyped-def]
    vault = tmp_path / "vault"
    create_scaffold(vault)
    report = run_doctor(AtlasConfig(), vault)
    by_name = {c.name: c for c in report.checks}
    assert by_name["vault:present"].status == "ok"
    assert by_name["vault:index.md"].status == "ok"
    assert by_name["vault:00-system/vault-charter.md"].status == "ok"
    # A freshly-initialized vault has no generated indexes yet: unknown, not error.
    assert by_name["vault:generated-indexes"].status == "unknown"
    assert report.ok is True


def test_vault_path_that_is_a_file_is_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    file_path = tmp_path / "not-a-dir"
    file_path.write_text("x", encoding="utf-8")
    report = run_doctor(AtlasConfig(), file_path)
    assert report.rollup == "error"
    assert report.ok is False


def test_render_text_is_ascii_and_deterministic() -> None:
    report = run_doctor(AtlasConfig())
    text = render_text(report)
    # ASCII-only keeps ruff (RUF001/RUF002) quiet and stdout portable.
    assert text.isascii()
    assert "atlas doctor" in text
    assert render_text(report) == text  # deterministic


def test_to_dict_is_json_serializable_with_sorted_keys() -> None:
    report = run_doctor(AtlasConfig())
    payload = to_dict(report)
    dumped = json.dumps(payload, sort_keys=True)
    restored = json.loads(dumped)
    assert restored["rollup"] == report.rollup
    assert restored["ok"] == report.ok
    assert isinstance(restored["checks"], list)
    assert {"name", "status", "detail"} == set(restored["checks"][0])


def test_cli_doctor_text_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["doctor"])
    out = capsys.readouterr().out
    assert code == 0
    assert "atlas doctor" in out
    assert "rollup:" in out


def test_cli_doctor_json_emits_valid_report(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["doctor", "--json"])
    out = capsys.readouterr().out
    assert code == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert any(c["name"] == "python-runtime" for c in payload["checks"])


def test_cli_doctor_with_scaffolded_vault(
    tmp_path,  # type: ignore[no-untyped-def]
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "vault"
    create_scaffold(vault)
    code = main(["doctor", "--vault", str(vault), "--json"])
    out = capsys.readouterr().out
    assert code == 0
    payload = json.loads(out)
    names = {c["name"] for c in payload["checks"]}
    assert "vault:present" in names
    assert "vault:index.md" in names
