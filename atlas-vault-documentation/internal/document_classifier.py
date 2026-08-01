"""Deterministic documentation classification for AS-WP-004."""

from __future__ import annotations

from pathlib import Path
from typing import Any

SUPPORTED_TEXT_EXTENSIONS = {
    ".md": "text/markdown", ".markdown": "text/markdown", ".txt": "text/plain",
    ".rst": "text/x-rst", ".json": "application/json", ".yaml": "application/yaml",
    ".yml": "application/yaml", ".toml": "application/toml",
}
SUPPORTED_NAMES = {"README", "README.md", "CHANGELOG", "LICENSE"}
GRAPHIFY_PARTS = ("graphify-out", "graph.json", "graph_report.md", "graph-report.md")


def _heading_signals(text: str) -> set[str]:
    headings = {line.lstrip("#").strip().lower() for line in text.splitlines() if line.startswith("#")}
    result: set[str] = set()
    for token, category in (
        ("requirement", "requirements"), ("architecture", "architecture"),
        ("decision", "architecture-decision"), ("roadmap", "roadmap"),
        ("validation", "validation-report"), ("test", "test-report"),
        ("security", "security"), ("work package", "work-package"),
        ("worklog", "worklog"), ("completion", "completion-report"),
        ("skill", "skill-definition"), ("agent", "agent-instruction"),
    ):
        if any(token in heading for heading in headings):
            result.add(category)
    return result


def classify(relative_path: str, *, text: str | None = None) -> dict[str, Any]:
    path = relative_path.replace("\\", "/")
    lower = path.lower()
    evidence: list[str] = []
    candidates: list[str] = []
    if any(part in lower for part in GRAPHIFY_PARTS) or "graphify-out/" in lower:
        return {"type": "graphify-output", "confidence": "high", "evidence": ["graphify-path"], "competing": [], "rule_version": "1"}
    for token, category in (
        ("requirements", "requirements"), ("architecture", "architecture"),
        ("adr", "architecture-decision"), ("decision", "architecture-decision"),
        ("roadmap", "roadmap"), ("validation", "validation-report"),
        ("test", "test-report"), ("security", "security"), ("threat", "threat-model"),
        ("deployment", "deployment"), ("operation", "operations"),
        ("worklog", "worklog"), ("prp", "implementation-plan"),
        ("skill", "skill-definition"), ("agent", "agent-instruction"),
        ("readme", "project-overview"),
    ):
        if token in lower:
            candidates.append(category)
            evidence.append("path-pattern")
    if text:
        candidates.extend(sorted(_heading_signals(text)))
        if _heading_signals(text):
            evidence.append("heading-signature")
    unique = list(dict.fromkeys(candidates))
    if not unique:
        selected, confidence = "unknown", "low"
    elif len(unique) == 1:
        selected, confidence = unique[0], "high" if "path-pattern" in evidence else "medium"
    else:
        selected, confidence = unique[0], "medium"
    return {
        "type": selected, "confidence": confidence, "evidence": list(dict.fromkeys(evidence)),
        "competing": unique[1:], "rule_version": "1",
    }


def media_type(path: Path) -> str | None:
    return SUPPORTED_TEXT_EXTENSIONS.get(path.suffix.lower())
