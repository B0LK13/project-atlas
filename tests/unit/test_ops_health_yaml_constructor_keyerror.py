"""Contain yaml.safe_load constructor KeyError in ops-health YAML reads.

``_read_yaml_mapping`` is a best-effort helper: missing or unreadable
files return ``None``. PyYAML ``!!bool nope`` raises a bare ``KeyError``,
not ``yaml.YAMLError``. On live main ``b87b4a22`` that leaked out of
``build_health_snapshot`` when ``.atlas/agent-readiness.yaml`` used a
constructor tag.

This package does not invent readiness. Does not touch ``ingestion.py``.
Sibling of #819 / #820 / #822 / #823 / #824 / #825.
"""

from __future__ import annotations

from pathlib import Path

from project_atlas.ops_health import _read_yaml_mapping, build_health_snapshot

MALFORMED = "atlas: !!bool nope\n"


def test_read_yaml_mapping_constructor_tag_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "agent-readiness.yaml"
    path.write_text(MALFORMED, encoding="utf-8")
    assert _read_yaml_mapping(path) is None


def test_health_snapshot_constructor_tag_does_not_raise(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / ".atlas").mkdir(parents=True)
    (vault / ".atlas" / "vault.json").write_text(
        '{"vault_id": "atlas-main", "vault_uuid": "fixture-vault-uuid"}\n',
        encoding="utf-8",
    )
    (vault / ".atlas" / "agent-readiness.yaml").write_text(MALFORMED, encoding="utf-8")
    snapshot = build_health_snapshot(vault)
    assert snapshot["truth_plane"] == "operational"
    assert snapshot["authority_plane"] == "none"
    signals = {item["signal_id"]: item for item in snapshot["signals"]}
    assert signals["OPS-SIG-010"]["status"] == "unknown"
