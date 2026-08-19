"""Tests for normalization orchestration (AS-009..AS-012, AS-019)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest

SUBPROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SUBPROJECT / "scripts"))
sys.path.insert(0, str(SUBPROJECT))

import capture_event  # noqa: E402
import normalize_event  # noqa: E402
from internal import normalization, provenance  # noqa: E402

_MDA_SCRIPT = SUBPROJECT / "tests" / "fixtures" / "bin" / "mda"
MOCK_MDA = _MDA_SCRIPT
EVENT_ID = "AE-20260801T100000Z-project-atlas-norm01"
OCCURRED = "2026-08-01T10:00:00Z"


@pytest.fixture()
def raw_event(vault: Path) -> Path:
    rc = capture_event.main([
        "--vault", str(vault),
        "--project-id", "PRJ-ATLAS",
        "--project-slug", "project-atlas",
        "--event-kind", "implementation",
        "--summary", "Normalization fixture",
        "--agent", "kimi-code",
        "--occurred-at", OCCURRED,
        "--event-id", EVENT_ID,
        "--result", "60 passed",
        "--command", "python -m pytest tests",
    ])
    assert rc == 0
    return next(vault.rglob(f"{EVENT_ID}.md"))


def normalize_args(raw: Path, *extra: str) -> list[str]:
    return [
        "--event", str(raw),
        "--mda-command", str(MOCK_MDA),
        "--timeout", "10",
        *extra,
    ]


# --- Successful normalization (AS-010 provenance) ------------------------------


class TestSuccessfulNormalization:
    def test_sibling_mode_end_to_end(
        self, raw_event: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        raw_hash_before = provenance.sha256_file(raw_event)
        assert normalize_event.main(normalize_args(raw_event, "--json")) == 0
        payload = json.loads(capsys.readouterr().out)

        assert payload["ok"] is True
        assert payload["status"] == "normalized"
        assert payload["event_id"] == EVENT_ID
        output = Path(payload["normalized_event"])
        assert output.name == f"AE-20260801T100000Z-project-atlas-norm01.restructured.md"
        assert output.parent == raw_event.parent

        # AS-009: raw evidence untouched.
        assert provenance.sha256_file(raw_event) == raw_hash_before

        text = output.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "atlas_provenance:" in text
        prov = payload["provenance"]
        assert prov["raw_event_id"] == EVENT_ID
        assert prov["raw_event_hash"] == f"sha256:{raw_hash_before}"
        assert prov["verification_status"] == "verified"
        assert prov["provider"] == "unknown"
        assert prov["output_mode"] == "sibling"
        assert prov["command_version"] == "mda 0.2.9-mock"
        assert prov["schema_version"] == 1
        assert "command_arguments" in prov
        args = prov["command_arguments"]
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
            except json.JSONDecodeError:
                parsed = args
            args = parsed
        if isinstance(args, list):
            assert str(MOCK_MDA) in [str(a) for a in args]
        else:
            assert str(MOCK_MDA) in str(args)
        # AS-010: normalized output references its raw source.
        assert f"source:agent-event:{EVENT_ID}" in text

    def test_fenced_output_stripped(self, raw_event: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "fenced")
        assert normalize_event.main(normalize_args(raw_event)) == 0
        output = next(raw_event.parent.glob("*.restructured.md"))
        assert output.read_text(encoding="utf-8").startswith("---\n")

    def test_directory_mode(self, raw_event: Path, vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
        outdir = vault / "projects" / "project-atlas" / "events"
        rc = normalize_event.main(normalize_args(
            raw_event, "--output-mode", "directory", "--output-dir", str(outdir), "--json",
        ))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        args = payload["provenance"]["command_arguments"]
        if isinstance(args, str):
            args = json.loads(args)
        assert "--out-dir" in args
        assert "--output-folder" not in args
        assert (outdir / f"{EVENT_ID}.restructured.md").is_file()

    def test_provider_from_env(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("ATLAS_PROVIDER", "local-llm")
        assert normalize_event.main(normalize_args(raw_event, "--json")) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["provenance"]["provider"] == "local-llm"

    def test_config_resolution(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Non-execution settings may come from discovered repo config; the
        # executable must still come from a trusted boundary (CLI here).
        (tmp_path / "atlas-agent.yaml").write_text(
            "normalization:\n"
            "  provider: config-provider\n"
            "  output_mode: sibling\n"
            "  timeout: 10\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        assert normalize_event.main([
            "--event", str(raw_event),
            "--mda-command", str(MOCK_MDA),
            "--json",
        ]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["provenance"]["provider"] == "config-provider"

    def test_cli_overrides_config(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        (tmp_path / "atlas-agent.yaml").write_text(
            "normalization:\n  provider: config-provider\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        assert normalize_event.main([
            "--event", str(raw_event),
            "--mda-command", str(MOCK_MDA),
            "--provider", "cli-provider",
            "--json",
        ]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["provenance"]["provider"] == "cli-provider"

    def test_record_command_disabled(
        self, raw_event: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = tmp_path / "atlas-agent.yaml"
        config.write_text("normalization:\n  record_command: false\n", encoding="utf-8")
        args = normalize_args(raw_event, "--config", str(config), "--json")
        assert normalize_event.main(args) == 0
        payload = json.loads(capsys.readouterr().out)
        assert "command_arguments" not in payload["provenance"]

    def test_dry_run_executes_nothing(
        self, raw_event: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        before = set(raw_event.parent.iterdir())
        assert normalize_event.main(normalize_args(raw_event, "--dry-run", "--json")) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "dry-run"
        assert str(MOCK_MDA) in [str(a) for a in payload["command"]]
        assert "--output-folder" not in payload["command"]
        assert payload["output_suffix"] == ".restructured.md"
        assert payload["output_contract"] == "CANONICAL_RESTRUCTURED"
        assert str(payload["expected_output"]).endswith(".restructured.md")
        assert set(raw_event.parent.iterdir()) == before

    def test_disabled_by_config(self, raw_event: Path, tmp_path: Path) -> None:
        config = tmp_path / "atlas-agent.yaml"
        config.write_text("normalization:\n  enabled: false\n", encoding="utf-8")
        rc = normalize_event.main(normalize_args(raw_event, "--config", str(config)))
        assert rc == 0
        assert list(raw_event.parent.glob("*.restructured.md")) == []

    def test_unicode_content(self, vault: Path) -> None:
        rc = capture_event.main([
            "--vault", str(vault),
            "--project-id", "PRJ-ATLAS",
            "--project-slug", "project-atlas",
            "--event-kind", "research",
            "--summary", "Unicode — héllo wörld — 知识",
            "--agent", "kimi-code",
            "--occurred-at", OCCURRED,
            "--event-id", "AE-20260801T100000Z-project-atlas-uni01",
        ])
        assert rc == 0
        raw = next(vault.rglob("*uni01.md"))
        assert normalize_event.main(normalize_args(raw)) == 0

    def test_long_paths(self, raw_event: Path, vault: Path) -> None:
        long_dir = vault / ("d" * 90) / ("e" * 90)
        rc = normalize_event.main(normalize_args(
            raw_event, "--output-mode", "directory", "--output-dir", str(long_dir),
        ))
        assert rc == 0
        assert (long_dir / f"{EVENT_ID}.restructured.md").is_file()


# --- Failure handling (AS-019 provider degradation) ----------------------------


class TestFailureHandling:
    def _failure_record(self, raw_event: Path) -> dict[str, Any]:
        record = raw_event.with_name(
            raw_event.name.replace(".md", ".normalization-failed.json")
        )
        assert record.is_file()
        return cast(dict[str, Any], json.loads(record.read_text(encoding="utf-8")))

    def test_executable_missing(self, raw_event: Path) -> None:
        rc = normalize_event.main([
            "--event", str(raw_event), "--mda-command", "/nonexistent/mda-cli",
        ])
        assert rc == 4
        record = self._failure_record(raw_event)
        assert record["category"] == "executable-missing"
        assert record["event_id"] == EVENT_ID
        # AS-019: raw evidence intact, normalization still pending.
        assert "normalization_state: pending" in raw_event.read_text(encoding="utf-8")

    def test_permission_denied(self, raw_event: Path, tmp_path: Path) -> None:
        if sys.platform == "win32":
            pytest.skip(
                "POSIX chmod non-executability is not reproducible on Win32 "
                "(WinError 193); covered on Linux CI"
            )
        fake = tmp_path / "not-executable"
        fake.write_text("#!/bin/sh\n", encoding="utf-8")
        fake.chmod(0o644)
        rc = normalize_event.main(["--event", str(raw_event), "--mda-command", str(fake)])
        assert rc == 4
        assert self._failure_record(raw_event)["category"] == "permission-denied"

    def test_timeout_with_retries(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "sleep")
        rc = normalize_event.main(normalize_args(
            raw_event, "--timeout", "0.5", "--retries", "1", "--json",
        ))
        assert rc == 4
        payload = json.loads(capsys.readouterr().out)
        assert payload["category"] == "timeout"
        assert payload["attempts"] == 2

    def test_provider_failure(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "exit-nonzero")
        rc = normalize_event.main(normalize_args(raw_event, "--json"))
        assert rc == 4
        payload = json.loads(capsys.readouterr().out)
        assert payload["category"] == "process-failed"
        assert "simulated outage" in payload["message"]
        assert list(raw_event.parent.glob("*.restructured.md")) == []

    def test_missing_output(self, raw_event: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "missing-output")
        assert normalize_event.main(normalize_args(raw_event)) == 4
        assert self._failure_record(raw_event)["category"] == "missing-output"

    def test_invalid_raw_event(self, vault: Path, raw_event: Path) -> None:
        text = raw_event.read_text(encoding="utf-8").replace(
            'event_kind: "implementation"', 'event_kind: "bogus"'
        )
        raw_event.write_text(text, encoding="utf-8")
        assert normalize_event.main(normalize_args(raw_event)) == 4
        assert self._failure_record(raw_event)["category"] == "invalid-raw-event"

    def test_missing_raw_event_file(self, vault: Path) -> None:
        rc = normalize_event.main(["--event", str(vault / "nope.md")])
        assert rc == 3

    @pytest.mark.parametrize("mode", ["bad-frontmatter", "wrong-type", "no-source", "secret-leak", "extra-file"])
    def test_verification_failures(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str], mode: str,
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", mode)
        rc = normalize_event.main(normalize_args(raw_event, "--json"))
        assert rc == 5
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["category"] == "verification-failed"
        assert payload["problems"], mode

    def test_secret_leak_not_repeated_in_output(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "secret-leak")
        rc = normalize_event.main(normalize_args(raw_event, "--json"))
        assert rc == 5
        stdout = capsys.readouterr().out
        assert "AKIA" not in stdout

    def test_output_exists_fails_before_execution(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "extra-file")
        expected = raw_event.with_name(raw_event.name.replace(".md", ".restructured.md"))
        expected.write_text("pre-existing content\n", encoding="utf-8")
        rc = normalize_event.main(normalize_args(raw_event))
        assert rc == 3
        # mda never ran: no unexpected side effects, original untouched.
        assert expected.read_text(encoding="utf-8") == "pre-existing content\n"
        assert not (raw_event.parent / "unexpected.md").exists()


# --- Security -----------------------------------------------------------------


class TestSecurity:
    @pytest.mark.parametrize("bad", ["ok; rm -rf ~", "../escape", "a/b", "$(whoami)", "x`id`y"])
    def test_malformed_provider_names_rejected(self, raw_event: Path, bad: str) -> None:
        rc = normalize_event.main(normalize_args(raw_event, "--provider", bad))
        assert rc == 2
        assert list(raw_event.parent.glob("*.restructured.md")) == []

    def test_symlink_raw_event_escape_blocked(self, vault: Path, tmp_path: Path, raw_event: Path) -> None:
        outside = tmp_path / "outside-event.md"
        outside.write_text(raw_event.read_text(encoding="utf-8"), encoding="utf-8")
        link = vault / "sources" / "agent-events" / "linked.md"
        link.symlink_to(outside)
        rc = normalize_event.main(normalize_args(link))
        assert rc == 3
        assert list(tmp_path.glob("*.restructured.md")) == []

    def test_output_dir_outside_root_blocked(self, raw_event: Path, tmp_path: Path) -> None:
        outside = tmp_path / "elsewhere"
        rc = normalize_event.main(normalize_args(
            raw_event, "--output-mode", "directory", "--output-dir", str(outside),
        ))
        assert rc == 3
        assert not outside.exists() or list(outside.rglob("*")) == []

    def test_no_shell_invocation(self, raw_event: Path) -> None:
        # The command builder must produce an argument array, and a raw
        # event path containing shell metacharacters must not execute.
        settings = normalization.NormalizationSettings(
            mda_command="mda", skill="s", skill_dir=None, provider="p",
            timeout_seconds=1, retries=0, output_mode="sibling",
            output_dir=None, verify=True, record_command=True, enabled=True,
        )
        argv = normalization.build_command(settings, Path("raw;rm -rf.md"))  # sibling: contract unused
        assert isinstance(argv, list)
        assert argv[-1] == "raw;rm -rf.md"  # passed as data, never a shell line
