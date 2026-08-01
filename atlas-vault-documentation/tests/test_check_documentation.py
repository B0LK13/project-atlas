"""Tests for documentation validation (AS-007, AS-008, JSON contract)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import capture_event  # noqa: E402
import check_documentation  # noqa: E402

OCCURRED = "2026-08-01T10:00:00Z"


def capture(vault: Path, event_id: str, kind: str = "validation") -> None:
    rc = capture_event.main([
        "--vault", str(vault),
        "--project-id", "PRJ-ATLAS",
        "--project-slug", "project-atlas",
        "--event-kind", kind,
        "--summary", "validation fixture",
        "--agent", "kimi-code",
        "--occurred-at", OCCURRED,
        "--event-id", event_id,
    ])
    assert rc == 0


def capture_spool(repo: Path, event_id: str) -> None:
    rc = capture_event.main([
        "--spool", str(repo),
        "--project-id", "PRJ-ATLAS",
        "--project-slug", "project-atlas",
        "--event-kind", "implementation",
        "--summary", "spooled work",
        "--agent", "kimi-code",
        "--occurred-at", OCCURRED,
        "--event-id", event_id,
    ])
    assert rc == 0


# --- AS-007 Strict spool gate ---------------------------------------------------


class TestStrictSpoolGate:
    def test_strict_fails_on_pending_spool(self, spool_repo: Path) -> None:
        capture_spool(spool_repo, "AE-20260801T100000Z-project-atlas-spool01")
        rc = check_documentation.main(["--spool-root", str(spool_repo), "--strict"])
        assert rc == 1

    def test_non_strict_reports_but_passes(
        self, spool_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        capture_spool(spool_repo, "AE-20260801T100000Z-project-atlas-spool01")
        rc = check_documentation.main(["--spool-root", str(spool_repo)])
        assert rc == 0
        assert "Pending spool: 1" in capsys.readouterr().out

    def test_strict_passes_when_spool_empty(self, spool_repo: Path) -> None:
        (spool_repo / ".atlas-spool").mkdir()
        assert check_documentation.main(["--spool-root", str(spool_repo), "--strict"]) == 0

    def test_clean_vault_passes_strict(self, vault: Path) -> None:
        capture(vault, "AE-20260801T100000Z-project-atlas-valid01")
        assert check_documentation.main(["--vault", str(vault), "--strict"]) == 0

    def test_strict_from_config(
        self, spool_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        capture_spool(spool_repo, "AE-20260801T100000Z-project-atlas-spool01")
        (tmp_path / "atlas-agent.yaml").write_text(
            f"atlas:\n  spool_root: {spool_repo}\n"
            "validation:\n  fail_completion_on_unsynced_spool: true\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        assert check_documentation.main([]) == 1

    def test_strict_from_env(
        self, spool_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        capture_spool(spool_repo, "AE-20260801T100000Z-project-atlas-spool01")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ATLAS_SPOOL_ROOT", str(spool_repo))
        monkeypatch.setenv("ATLAS_STRICT", "true")
        assert check_documentation.main([]) == 1


# --- AS-008 Controlled taxonomy (validator side) --------------------------------


class TestValidatorTaxonomy:
    def test_unsupported_kind_flagged(self, vault: Path) -> None:
        capture(vault, "AE-20260801T100000Z-project-atlas-valid01")
        target = next(vault.rglob("*.md"))
        text = target.read_text(encoding="utf-8").replace(
            'event_kind: "validation"', 'event_kind: "not-a-kind"'
        )
        target.write_text(text, encoding="utf-8")
        assert check_documentation.main(["--vault", str(vault)]) == 1

    def test_secret_bearing_event_flagged(self, vault: Path) -> None:
        capture(vault, "AE-20260801T100000Z-project-atlas-valid01")
        target = next(vault.rglob("*.md"))
        target.write_text(
            target.read_text(encoding="utf-8") + "\nAKIAIOSFODNN7EXAMPLE\n",
            encoding="utf-8",
        )
        assert check_documentation.main(["--vault", str(vault)]) == 1

    def test_missing_required_keys_flagged(self, vault: Path) -> None:
        capture(vault, "AE-20260801T100000Z-project-atlas-valid01")
        target = next(vault.rglob("*.md"))
        text = target.read_text(encoding="utf-8").replace(
            'event_kind: "validation"\n', ""
        )
        target.write_text(text, encoding="utf-8")
        assert check_documentation.main(["--vault", str(vault)]) == 1

    def test_self_asserted_verified_flagged(self, vault: Path) -> None:
        capture(vault, "AE-20260801T100000Z-project-atlas-valid01")
        target = next(vault.rglob("*.md"))
        text = target.read_text(encoding="utf-8").replace(
            "review_state: generated", "review_state: verified"
        )
        target.write_text(text, encoding="utf-8")
        assert check_documentation.main(["--vault", str(vault)]) == 1

    def test_malformed_frontmatter_flagged(self, vault: Path) -> None:
        broken = vault / "sources" / "agent-events" / "2026" / "08" / "01" / "broken.md"
        broken.parent.mkdir(parents=True)
        broken.write_text("# no frontmatter at all\n", encoding="utf-8")
        assert check_documentation.main(["--vault", str(vault)]) == 1


# --- JSON output contract --------------------------------------------------------


class TestJsonContract:
    def test_clean_payload(self, vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
        capture(vault, "AE-20260801T100000Z-project-atlas-valid01")
        capsys.readouterr()
        assert check_documentation.main(["--vault", str(vault), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload) == {
            "ok", "files_checked", "raw_checked", "normalized_checked",
            "pending_spool", "errors",
        }
        assert payload["ok"] is True
        assert payload["files_checked"] == 1
        assert payload["raw_checked"] == 1
        assert payload["normalized_checked"] == 0
        assert payload["pending_spool"] == 0
        assert payload["errors"] == []

    def test_strict_spool_payload(
        self, spool_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        capture_spool(spool_repo, "AE-20260801T100000Z-project-atlas-spool01")
        capsys.readouterr()
        rc = check_documentation.main(
            ["--spool-root", str(spool_repo), "--strict", "--json"]
        )
        assert rc == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["pending_spool"] == 1
        assert any("spool" in error for error in payload["errors"])

    def test_no_targets_is_usage_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)  # no config discoverable here
        assert check_documentation.main([]) == 2


# --- Normalized event validation ------------------------------------------------


class TestNormalizedEventValidation:
    def _write_normalized(self, vault: Path, *, provenance: bool = True) -> Path:
        target = (
            vault / "sources" / "agent-events" / "2026" / "08" / "01"
            / "AE-20260801T100000Z-project-atlas-norm01.normalized.md"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        prov_block = (
            "atlas_provenance:\n"
            "  schema_version: 1\n"
            '  raw_event_id: "AE-20260801T100000Z-project-atlas-norm01"\n'
            '  raw_event_hash: "sha256:abc"\n'
            '  verification_status: "verified"\n'
            if provenance
            else ""
        )
        target.write_text(
            "---\n"
            "type: Agent Work Event\n"
            'id: "agent-event:AE-20260801T100000Z-project-atlas-norm01"\n'
            'project_id: "PRJ-ATLAS"\n'
            'event_kind: "implementation"\n'
            'status: "completed"\n'
            "sources:\n"
            '  - id: "source:agent-event:AE-20260801T100000Z-project-atlas-norm01"\n'
            f"{prov_block}"
            "---\n\n# Normalized\n",
            encoding="utf-8",
        )
        return target

    def test_valid_normalized_event_passes(self, vault: Path) -> None:
        self._write_normalized(vault)
        assert check_documentation.main(["--vault", str(vault)]) == 0

    def test_raw_rules_not_applied_to_normalized(self, vault: Path) -> None:
        """Normalized events legitimately lack raw-only keys (captured_at,
        normalization_state, knowledge_state: source)."""
        target = self._write_normalized(vault)
        assert "captured_at" not in target.read_text(encoding="utf-8")
        assert check_documentation.main(["--vault", str(vault)]) == 0

    def test_missing_provenance_flagged(self, vault: Path) -> None:
        self._write_normalized(vault, provenance=False)
        assert check_documentation.main(["--vault", str(vault)]) == 1

    def test_wrong_type_flagged(self, vault: Path) -> None:
        target = self._write_normalized(vault)
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "type: Agent Work Event", "type: Document"
            ),
            encoding="utf-8",
        )
        assert check_documentation.main(["--vault", str(vault)]) == 1
