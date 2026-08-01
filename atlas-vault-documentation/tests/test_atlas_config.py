"""Tests for configuration discovery and environment fallback."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import atlas_config  # noqa: E402


class TestParseConfigText:
    def test_two_level_maps_and_scalars(self) -> None:
        config = atlas_config.parse_config_text(
            "# comment\n"
            "version: 1\n"
            "atlas:\n"
            "  vault: /srv/vault\n"
            "  project_id: PRJ-EXAMPLE\n"
            "capture:\n"
            "  immediate: true\n"
            "  skill_dir: null\n"
        )
        assert config["version"] == {"": 1}
        assert config["atlas"]["vault"] == "/srv/vault"
        assert config["capture"]["immediate"] is True
        assert config["capture"]["skill_dir"] is None

    def test_quoted_values_and_inline_comments(self) -> None:
        config = atlas_config.parse_config_text(
            'agent:\n  id: "kimi-code"  # trailing comment\n'
        )
        assert config["agent"]["id"] == "kimi-code"

    def test_lists_rejected(self) -> None:
        with pytest.raises(atlas_config.ConfigError):
            atlas_config.parse_config_text("atlas:\n  - item\n")

    def test_indented_key_without_section_rejected(self) -> None:
        with pytest.raises(atlas_config.ConfigError):
            atlas_config.parse_config_text("  orphan: value\n")

    def test_garbage_rejected(self) -> None:
        with pytest.raises(atlas_config.ConfigError):
            atlas_config.parse_config_text("no colon here\n")


class TestDiscovery:
    def test_find_config_walks_upward(self, tmp_path: Path) -> None:
        (tmp_path / "atlas-agent.yaml").write_text("atlas:\n  vault: /x\n", encoding="utf-8")
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        assert atlas_config.find_config(nested) == tmp_path / "atlas-agent.yaml"

    def test_find_config_dotfile_variant(self, tmp_path: Path) -> None:
        (tmp_path / ".atlas-agent.yaml").write_text("atlas: {}\n", encoding="utf-8")
        assert atlas_config.find_config(tmp_path) is not None

    def test_find_config_missing(self, tmp_path: Path) -> None:
        assert atlas_config.find_config(tmp_path) is None

    def test_load_explicit_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(atlas_config.ConfigError):
            atlas_config.load_config(tmp_path / "missing.yaml")

    def test_load_returns_path_used(self, tmp_path: Path) -> None:
        path = tmp_path / "atlas-agent.yaml"
        path.write_text("atlas:\n  vault: /x\n", encoding="utf-8")
        config, used = atlas_config.load_config(start=tmp_path)
        assert used == path
        assert config["atlas"]["vault"] == "/x"

    def test_load_without_config_is_empty(self, tmp_path: Path) -> None:
        config, used = atlas_config.load_config(start=tmp_path)
        assert config == {}
        assert used is None


class TestResolve:
    def test_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        config = {"atlas": {"vault": "/from-config"}}
        monkeypatch.setenv("ATLAS_VAULT", "/from-env")
        assert atlas_config.resolve("/from-cli", "ATLAS_VAULT", config, "atlas", "vault") == "/from-cli"
        assert atlas_config.resolve(None, "ATLAS_VAULT", config, "atlas", "vault") == "/from-env"
        monkeypatch.delenv("ATLAS_VAULT")
        assert atlas_config.resolve(None, "ATLAS_VAULT", config, "atlas", "vault") == "/from-config"
        assert atlas_config.resolve(None, "ATLAS_VAULT", {}, "atlas", "vault", "/default") == "/default"

    def test_missing_everywhere_returns_default(self) -> None:
        assert atlas_config.resolve(None, "ATLAS_UNSET_VAR", {}, "a", "b") is None
