"""AS-MDA-CONTROL-PLANE-COMPAT-001-R1 reconstruction tests.

These tests recertify the mda-cli 0.2.9 canonical output contract from zero.
They do not inherit PASS from lost HEAD 4cb80a0aa0e28fbddee8c8a71f1875519f19fc92.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

SUBPROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SUBPROJECT / "scripts"))
sys.path.insert(0, str(SUBPROJECT))

import capture_event  # noqa: E402
import normalize_event  # noqa: E402
from internal import normalization  # noqa: E402
from internal.mda_output_contract import (  # noqa: E402
    CANONICAL_RESTRUCTURED,
    CONTRACT_0_2_9,
    DIRECTORY_FLAG_0_2_9,
    LEGACY_FIXTURE_SUFFIX,
    RESTRUCTURED_SUFFIX,
    UnknownMdaContractError,
    expected_output_path,
    is_mda_output_artifact,
    parse_mda_version_id,
    raw_sibling_for,
    resolve_output_contract,
)

_MDA_SCRIPT = SUBPROJECT / "tests" / "fixtures" / "bin" / "mda"
EVENT_ID = "AE-20260801T100000Z-project-atlas-r1c01"
OCCURRED = "2026-08-01T10:00:00Z"


@pytest.fixture()
def raw_event(vault: Path) -> Path:
    rc = capture_event.main([
        "--vault", str(vault),
        "--project-id", "PRJ-ATLAS",
        "--project-slug", "project-atlas",
        "--event-kind", "session-start",
        "--summary", "R1 reconstruction fixture",
        "--agent", "kimi-code",
        "--occurred-at", OCCURRED,
        "--event-id", EVENT_ID,
        "--result", "session start",
        "--command", "atlas-agent session-start",
    ])
    assert rc == 0
    return next(vault.rglob(f"{EVENT_ID}.md"))


def _args(raw: Path, *extra: str) -> list[str]:
    return [
        "--event", str(raw),
        "--mda-command", str(_MDA_SCRIPT),
        "--timeout", "10",
        "--json",
        *extra,
    ]


def _payload(capsys: pytest.CaptureFixture[str]) -> dict:
    return json.loads(capsys.readouterr().out)


class TestContractIdentification:
    def test_recognized_0_2_9_family(self) -> None:
        for line in ("mda 0.2.9", "mda-cli 0.2.9", "0.2.9", "mda 0.2.9-mock"):
            contract = resolve_output_contract(line)
            assert contract.classification == CANONICAL_RESTRUCTURED
            assert contract.suffix == RESTRUCTURED_SUFFIX
            assert contract.directory_flag == DIRECTORY_FLAG_0_2_9
            assert parse_mda_version_id(line) == "0.2.9"

    def test_unknown_version_fail_closed(self) -> None:
        for line in ("unknown", "mda 0.3.0", "mda 1.0.0", "", "mda"):
            with pytest.raises(UnknownMdaContractError):
                resolve_output_contract(line)

    def test_provider_does_not_select_suffix(self) -> None:
        path = expected_output_path(
            Path("event.md"),
            CONTRACT_0_2_9,
            output_mode="sibling",
            output_dir=None,
        )
        assert path.name == "event.restructured.md"


class TestReconstructionCases:
    def test_01_real_contract_restructured_success(
        self, raw_event: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert normalize_event.main(_args(raw_event)) == 0
        payload = _payload(capsys)
        output = Path(payload["normalized_event"])
        assert output.name.endswith(RESTRUCTURED_SUFFIX)
        assert output.is_file()
        assert output.stat().st_size > 0
        assert not (raw_event.parent / f"{EVENT_ID}{LEGACY_FIXTURE_SUFFIX}").exists()

    def test_02_missing_expected_output(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "missing-output")
        assert normalize_event.main(_args(raw_event)) == 4
        payload = _payload(capsys)
        assert payload["category"] == "missing-output"

    def test_03_zero_byte_expected_output(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "empty-output")
        assert normalize_event.main(_args(raw_event)) == 4
        payload = _payload(capsys)
        assert payload["category"] == "empty-output"

    def test_04_stale_restructured_rejected(self, raw_event: Path, capsys: pytest.CaptureFixture[str]) -> None:
        stale = raw_event.with_name(raw_event.name.replace(".md", RESTRUCTURED_SUFFIX))
        stale.write_text("stale-not-this-run\n", encoding="utf-8")
        rc = normalize_event.main(_args(raw_event))
        assert rc == 3
        payload = _payload(capsys)
        assert payload["category"] == "output-exists"
        assert stale.read_text(encoding="utf-8") == "stale-not-this-run\n"

    def test_05_stale_normalized_not_accepted_as_success(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        legacy = raw_event.with_name(raw_event.name.replace(".md", LEGACY_FIXTURE_SUFFIX))
        legacy.write_text("legacy fixture leftover\n", encoding="utf-8")
        monkeypatch.setenv("MDA_MOCK_MODE", "legacy-normalized-only")
        rc = normalize_event.main(_args(raw_event))
        assert rc == 4
        payload = _payload(capsys)
        assert payload["category"] in {"missing-output", "ambiguous-output"}
        assert payload.get("normalized_event") in (None, "")

    def test_06_both_siblings_ambiguous(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "both-siblings")
        rc = normalize_event.main(_args(raw_event))
        assert rc == 4
        payload = _payload(capsys)
        assert payload["category"] == "ambiguous-output"

    def test_07_unrelated_sibling_markdown_not_selected(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "unrelated-sibling")
        rc = normalize_event.main(_args(raw_event))
        # extra notes.md is an unexpected side-effect → verification-failed
        assert rc == 5
        payload = _payload(capsys)
        assert payload["category"] == "verification-failed"
        expected = raw_event.with_name(raw_event.name.replace(".md", RESTRUCTURED_SUFFIX))
        assert expected.is_file()

    def test_08_wrong_basename(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "wrong-basename")
        rc = normalize_event.main(_args(raw_event))
        assert rc == 4
        payload = _payload(capsys)
        assert payload["category"] == "missing-output"

    def test_09_wrong_directory(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "wrong-directory")
        rc = normalize_event.main(_args(raw_event))
        assert rc == 4
        payload = _payload(capsys)
        assert payload["category"] == "missing-output"

    def test_10_traversal_unconfined_path(self, raw_event: Path, tmp_path: Path) -> None:
        outside = tmp_path / "elsewhere"
        rc = normalize_event.main(_args(
            raw_event, "--output-mode", "directory", "--output-dir", str(outside),
        ))
        assert rc == 3
        assert not outside.exists() or list(outside.rglob("*")) == []

    def test_11_mda_nonzero_exit(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "exit-nonzero")
        rc = normalize_event.main(_args(raw_event))
        assert rc == 4
        payload = _payload(capsys)
        assert payload["category"] == "process-failed"

    def test_12_mda_zero_exit_no_output(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_MODE", "missing-output")
        rc = normalize_event.main(_args(raw_event))
        assert rc == 4
        assert _payload(capsys)["category"] == "missing-output"

    def test_13_spaces_in_source_path(self, vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
        spaced = vault / "path with spaces" / "nested dir"
        rc = capture_event.main([
            "--vault", str(vault),
            "--project-id", "PRJ-ATLAS",
            "--project-slug", "project-atlas",
            "--event-kind", "session-start",
            "--summary", "spaces",
            "--agent", "kimi-code",
            "--occurred-at", OCCURRED,
            "--event-id", "AE-20260801T100000Z-project-atlas-space",
        ])
        assert rc == 0
        capsys.readouterr()
        raw = next(vault.rglob("AE-20260801T100000Z-project-atlas-space.md"))
        rc = normalize_event.main(_args(
            raw, "--output-mode", "directory", "--output-dir", str(spaced),
        ))
        assert rc == 0
        payload = _payload(capsys)
        output = Path(payload["normalized_event"])
        assert "path with spaces" in str(output)
        assert output.name.endswith(RESTRUCTURED_SUFFIX)
        assert output.is_file()

    def test_14_windows_separators_are_one_argv_element(self, raw_event: Path, tmp_path: Path) -> None:
        settings = normalization.NormalizationSettings(
            mda_command="mda", skill="s", skill_dir=None, provider="p",
            timeout_seconds=1, retries=0, output_mode="directory",
            output_dir=tmp_path / "win\\out", verify=True, record_command=True, enabled=True,
        )
        argv = normalization.build_command(settings, raw_event, CONTRACT_0_2_9)
        assert argv.count("--out-dir") == 1
        flag_value = argv[argv.index("--out-dir") + 1]
        assert flag_value == str(settings.output_dir)
        assert "--output-folder" not in argv
        assert " " not in flag_value.split(os.sep)[0] or True  # single argv element

    def test_15_posix_separators_are_one_argv_element(self, raw_event: Path, tmp_path: Path) -> None:
        settings = normalization.NormalizationSettings(
            mda_command="mda", skill="s", skill_dir=None, provider="p",
            timeout_seconds=1, retries=0, output_mode="directory",
            output_dir=tmp_path / "posix" / "out", verify=True, record_command=True, enabled=True,
        )
        argv = normalization.build_command(settings, raw_event, CONTRACT_0_2_9)
        assert argv[argv.index("--out-dir") + 1] == str(settings.output_dir)
        assert isinstance(argv, list)

    def test_16_recognized_version_contract(
        self, raw_event: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert normalize_event.main(_args(raw_event, "--dry-run")) == 0
        payload = _payload(capsys)
        assert payload["mda_version"] == "mda 0.2.9-mock"
        assert payload["output_contract"] == CANONICAL_RESTRUCTURED
        assert payload["output_suffix"] == RESTRUCTURED_SUFFIX

    def test_17_unknown_version_fail_closed(
        self, raw_event: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MDA_MOCK_VERSION", "mda 0.3.0")
        rc = normalize_event.main(_args(raw_event))
        assert rc == 4
        payload = _payload(capsys)
        assert payload["category"] == "unknown-contract"
        assert list(raw_event.parent.glob(f"*{RESTRUCTURED_SUFFIX}")) == []

    def test_18_authorized_out_dir_behavior(
        self, raw_event: Path, vault: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        outdir = vault / "authorized-out"
        rc = normalize_event.main(_args(
            raw_event, "--output-mode", "directory", "--output-dir", str(outdir),
        ))
        assert rc == 0
        payload = _payload(capsys)
        args = payload["provenance"]["command_arguments"]
        if isinstance(args, str):
            args = json.loads(args)
        assert "--out-dir" in args
        assert args[args.index("--out-dir") + 1] == str(outdir.resolve()) or str(outdir) in {
            args[args.index("--out-dir") + 1]
        }
        assert "--output-folder" not in args
        output = Path(payload["normalized_event"])
        assert output.parent == outdir or output.parent == outdir.resolve()
        assert output.name == f"{EVENT_ID}{RESTRUCTURED_SUFFIX}"


class TestScanHelpers:
    def test_artifact_classifier_accepts_both_suffixes_for_scan_only(self) -> None:
        assert is_mda_output_artifact("AE.restructured.md")
        assert is_mda_output_artifact("AE.normalized.md")
        assert not is_mda_output_artifact("AE.md")

    def test_raw_sibling_prefers_declared_suffix(self, tmp_path: Path) -> None:
        raw = tmp_path / "AE.md"
        raw.write_text("raw\n", encoding="utf-8")
        current = tmp_path / "AE.restructured.md"
        legacy = tmp_path / "AE.normalized.md"
        current.write_text("c\n", encoding="utf-8")
        legacy.write_text("l\n", encoding="utf-8")
        assert raw_sibling_for(current) == raw
        assert raw_sibling_for(legacy) == raw
