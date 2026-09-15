"""Tests for deterministic raw-event capture (AS-002..AS-006, AS-008, AS-018)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import atlas_config  # noqa: E402
import capture_event  # noqa: E402

OCCURRED = "2026-08-01T10:00:00Z"


def base_args(vault: Path, event_id: str = "AE-20260801T100000Z-project-atlas-test01") -> list[str]:
    return [
        "--vault", str(vault),
        "--project-id", "PRJ-ATLAS",
        "--project-slug", "project-atlas",
        "--event-kind", "implementation",
        "--summary", "Deterministic capture hardening",
        "--agent", "kimi-code",
        "--occurred-at", OCCURRED,
        "--event-id", event_id,
    ]


def event_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.md"))


# --- AS-002 Immediate raw capture -------------------------------------------


class TestImmediateCapture:
    def test_writes_one_date_partitioned_event(self, vault: Path) -> None:
        assert capture_event.main(base_args(vault)) == 0
        expected = (
            vault / "sources" / "agent-events" / "2026" / "08" / "01"
            / "AE-20260801T100000Z-project-atlas-test01.md"
        )
        assert expected.is_file()
        assert event_files(vault) == [expected]

    def test_atomic_write_leaves_no_temp_files(self, vault: Path) -> None:
        assert capture_event.main(base_args(vault)) == 0
        leftovers = [p for p in vault.rglob("*") if p.name.endswith(".tmp")]
        assert leftovers == []

    def test_frontmatter_marks_captured_state(self, vault: Path) -> None:
        assert capture_event.main(base_args(vault)) == 0
        text = event_files(vault)[0].read_text(encoding="utf-8")
        assert "sync_state: captured" in text
        assert "normalization_state: pending" in text
        assert "knowledge_state: source" in text


# --- AS-003 Stable event ID ---------------------------------------------------


class TestStableEventId:
    def test_explicit_id_preserved_in_path_and_frontmatter(self, vault: Path) -> None:
        event_id = "AE-20260801T100000Z-project-atlas-stable99"
        assert capture_event.main(base_args(vault, event_id)) == 0
        path = event_files(vault)[0]
        assert path.name == f"{event_id}.md"
        assert f'event_id: "{event_id}"' in path.read_text(encoding="utf-8")

    def test_id_unchanged_through_validation(self, vault: Path) -> None:
        import check_documentation

        event_id = "AE-20260801T100000Z-project-atlas-stable99"
        assert capture_event.main(base_args(vault, event_id)) == 0
        before = event_files(vault)[0].read_bytes()
        assert check_documentation.main(["--vault", str(vault), "--strict"]) == 0
        after = event_files(vault)[0].read_bytes()
        assert before == after
        assert f'event_id: "{event_id}"'.encode() in after


# --- AS-004 No silent overwrite ----------------------------------------------


class TestDuplicateEventId:
    def test_duplicate_fails_closed_and_preserves_original(
        self, vault: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = base_args(vault)
        assert capture_event.main(args) == 0
        original = event_files(vault)[0].read_bytes()

        changed = list(args)
        changed[changed.index("--summary") + 1] = "A different payload entirely"
        assert capture_event.main(changed) == 3
        assert event_files(vault)[0].read_bytes() == original
        assert "already exists" in capsys.readouterr().err

    def test_duplicate_json_error_contract(
        self, vault: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = base_args(vault)
        assert capture_event.main(args) == 0
        capsys.readouterr()
        assert capture_event.main([*args, "--json"]) == 3
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert isinstance(payload["error"], str)
        assert set(payload) == {"ok", "error"}


# --- AS-005 Secret redaction --------------------------------------------------

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "secret-event-input.txt"


def _fixture_secrets() -> list[str]:
    secrets_found: list[str] = []
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("summary"):
            secrets_found.append(line.split("=", 1)[1].strip())
    return secrets_found


class TestSecretRedaction:
    def test_fixture_secrets_never_persisted(
        self, vault: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        secrets_in_fixture = _fixture_secrets()
        assert len(secrets_in_fixture) == 2
        args = base_args(vault) + [
            "--outcome", f"credentials observed: {secrets_in_fixture[0]}",
            "--command", "deploy --token placeholder",
            "--result", f"authenticated with {secrets_in_fixture[1]}",
            "--json",
        ]
        assert capture_event.main(args) == 0
        persisted = event_files(vault)[0].read_text(encoding="utf-8")
        stdout = capsys.readouterr().out
        for secret in secrets_in_fixture:
            assert secret not in persisted
            assert secret not in stdout
        assert "[REDACTED SECRET]" in persisted

    @pytest.mark.parametrize(
        "sample",
        [
            "key sk-proj-abcdefghijklmnop1234 end",
            "token ghp_ABCDEFGHIJKLMNOPQRST1234 end",
            "aws AKIAIOSFODNN7EXAMPLE end",
            "api_key=supersecretvalue123",
            "token: anothersecretvalue456",
            "password=hunter2hunter2",
        ],
    )
    def test_redact_patterns(self, sample: str) -> None:
        redacted = capture_event.redact(sample)
        assert "[REDACTED SECRET]" in redacted
        # The secret-shaped material is gone; never print it here.
        assert redacted != sample

    def test_redact_private_key_block(self) -> None:
        sample = (
            "-----BEGIN PRIVATE KEY-----\nFAKE-KEY-MATERIAL\n"
            "-----END PRIVATE KEY-----"
        )
        redacted = capture_event.redact(sample)
        assert "FAKE-KEY-MATERIAL" not in redacted
        assert "[REDACTED SECRET]" in redacted

    def test_error_messages_are_redacted(self) -> None:
        secret = _fixture_secrets()[0]
        message = capture_event.redact(f"unsafe output path outside root: /tmp/{secret}/x")
        assert secret not in message


# --- AS-006 Spool fallback ----------------------------------------------------


class TestSpoolFallback:
    def test_spool_capture_marks_pending(self, spool_repo: Path) -> None:
        args = base_args(spool_repo)
        args[args.index("--vault")] = "--spool"
        assert capture_event.main(args) == 0
        expected = spool_repo / ".atlas-spool" / "AE-20260801T100000Z-project-atlas-test01.md"
        assert expected.is_file()
        text = expected.read_text(encoding="utf-8")
        assert "sync_state: pending" in text


# --- AS-008 Controlled taxonomy -----------------------------------------------


class TestControlledTaxonomy:
    def test_unsupported_kind_rejected_at_cli(self, vault: Path) -> None:
        args = base_args(vault)
        args[args.index("--event-kind") + 1] = "not-a-kind"
        with pytest.raises(SystemExit) as excinfo:
            capture_event.main(args)
        assert excinfo.value.code == 2
        assert event_files(vault) == []

    def test_taxonomy_matches_standard(self) -> None:
        standard = (
            Path(__file__).resolve().parent.parent / "MDA-STANDARD.md"
        ).read_text(encoding="utf-8")
        for kind in capture_event.EVENT_KINDS:
            assert re.search(rf"^{re.escape(kind)}$", standard, re.M), kind


# --- AS-018 Path safety --------------------------------------------------------


class TestPathSafety:
    @pytest.mark.parametrize("bad_id", ["../evil", "..\\evil", "a/b", "a\\b", ".."])
    def test_traversal_event_ids_rejected(self, vault: Path, bad_id: str) -> None:
        assert capture_event.main(base_args(vault, bad_id)) == 2
        assert event_files(vault) == []

    def test_ensure_descendant_blocks_escape(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        with pytest.raises(ValueError, match="outside root"):
            capture_event.ensure_descendant(root, tmp_path / "escape.md")

    def test_ensure_descendant_allows_nested(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        capture_event.ensure_descendant(root, root / "a" / "b" / "event.md")

    def test_symlink_escape_blocked(self, vault: Path, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        link = vault / "sources"
        link.symlink_to(outside)
        # The resolved destination leaves the vault root; capture must fail.
        rc = capture_event.main(base_args(vault))
        assert rc == 3
        assert list(outside.rglob("*.md")) == []


# --- JSON output contract ------------------------------------------------------


class TestJsonContract:
    def test_success_payload(self, vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert capture_event.main([*base_args(vault), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload) == {"ok", "event_id", "path", "sync_state", "normalization_state", "bytes"}
        assert payload["ok"] is True
        assert payload["sync_state"] == "captured"
        assert payload["normalization_state"] == "pending"
        assert isinstance(payload["bytes"], int) and payload["bytes"] > 0
        assert Path(payload["path"]).is_file()


# --- Configuration discovery and environment fallback -------------------------


class TestConfigAndEnvFallback:
    def test_env_fallback(
        self, vault: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ATLAS_VAULT", str(vault))
        monkeypatch.setenv("ATLAS_PROJECT_ID", "PRJ-ENV")
        monkeypatch.setenv("ATLAS_PROJECT_SLUG", "env-project")
        monkeypatch.setenv("ATLAS_AGENT", "env-agent")
        rc = capture_event.main([
            "--event-kind", "plan", "--summary", "env fallback",
            "--occurred-at", OCCURRED,
        ])
        assert rc == 0
        text = event_files(vault)[0].read_text(encoding="utf-8")
        assert 'project_id: "PRJ-ENV"' in text
        assert 'agent: "env-agent"' in text

    def test_config_discovery(
        self, vault: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        (tmp_path / "atlas-agent.yaml").write_text(
            "atlas:\n"
            f"  vault: {vault}\n"
            "  project_id: PRJ-CONFIG\n"
            "  project_slug: config-project\n"
            "agent:\n"
            "  id: config-agent\n",
            encoding="utf-8",
        )
        nested = tmp_path / "deep" / "deeper"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)  # discovery must walk upward
        rc = capture_event.main([
            "--event-kind", "plan", "--summary", "config discovery",
            "--occurred-at", OCCURRED,
        ])
        assert rc == 0
        text = event_files(vault)[0].read_text(encoding="utf-8")
        assert 'project_id: "PRJ-CONFIG"' in text
        assert 'agent: "config-agent"' in text

    def test_cli_beats_env_beats_config(
        self, vault: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        (tmp_path / "atlas-agent.yaml").write_text(
            f"atlas:\n  vault: {vault}\n  project_id: PRJ-CONFIG\n"
            "  project_slug: config-project\nagent:\n  id: config-agent\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ATLAS_PROJECT_ID", "PRJ-ENV")
        args = [
            "--event-kind", "plan", "--summary", "precedence",
            "--occurred-at", OCCURRED, "--project-id", "PRJ-CLI",
        ]
        assert capture_event.main(args) == 0
        assert 'project_id: "PRJ-CLI"' in event_files(vault)[0].read_text(encoding="utf-8")

        args[args.index("--project-id")] = "--work-package"  # drop CLI override
        assert capture_event.main(args) == 0
        combined = "\n".join(p.read_text(encoding="utf-8") for p in event_files(vault))
        assert 'project_id: "PRJ-ENV"' in combined

    def test_missing_required_settings_fail_with_usage_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        rc = capture_event.main(["--event-kind", "plan", "--summary", "nothing configured"])
        assert rc == 2

    def test_explicit_missing_config_file_fails(self, tmp_path: Path) -> None:
        rc = capture_event.main([
            "--config", str(tmp_path / "nope.yaml"),
            "--event-kind", "plan", "--summary", "x",
        ])
        assert rc == 2
