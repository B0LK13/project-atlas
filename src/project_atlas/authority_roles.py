"""Deterministic artifact-role resolution for AS-CORE-006.

Roles are derived from structured YAML receipt semantics and governed path
shapes — not from self-asserted “canonical” wording or weak filename guesses.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from project_atlas.domain.authority_semantics import ArtifactRole

_PACKAGE_RE = re.compile(r"^wp:(.+)$")
_GENESIS_RECEIPT_PATH_RE = re.compile(
    r"^docs/evidence/([A-Za-z0-9][A-Za-z0-9._-]*)-receipt\.ya?ml$",
    re.I,
)
_REMEDIATION_PATH_MARKERS = (
    "-remediation-",
    "remediation-receipt",
    "wiring-receipt",
    "retired-slot",
    "-review.yaml",
    "-review.yml",
    "review-addendum",
)
_REMEDIATION_YAML_KEYS = frozenset(
    {
        "previous_implementation",
        "previous_blocked_candidate",
        "original_blocked_candidate",
        "remediation_implementation_commit",
        "previous_evidence",
    }
)


def _safe_yaml_root(text: str) -> dict[str, Any] | None:
    try:
        loaded = yaml.safe_load(text)
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def _package_id_from_subject(subject: str) -> str | None:
    match = _PACKAGE_RE.match(subject)
    return match.group(1) if match else None


def _has_nested_key(root: dict[str, Any], key: str) -> bool:
    if key in root:
        return True
    return any(isinstance(value, dict) and key in value for value in root.values())


def resolve_artifact_role(
    *,
    path: str,
    text: str,
    subject: str,
) -> ArtifactRole:
    """Resolve the artifact role for one source relative to a WP subject.

    Returns UNKNOWN when structured evidence is insufficient for a safe role.
    Self-asserted wording such as “canonical” / “authoritative” never grants
    a registry-eligible role by itself.
    """
    normalized = path.replace("\\", "/")
    package_id = _package_id_from_subject(subject)
    if package_id is None:
        return ArtifactRole.UNKNOWN

    root = _safe_yaml_root(text) or {}
    declared_package = root.get("package") or root.get("work_package")
    if isinstance(declared_package, str) and declared_package != package_id:
        # Document is about a different package — not eligible for this subject.
        return ArtifactRole.UNKNOWN

    path_lower = normalized.lower()
    remediation_path = any(marker in path_lower for marker in _REMEDIATION_PATH_MARKERS)
    remediation_yaml = any(_has_nested_key(root, key) for key in _REMEDIATION_YAML_KEYS)
    if remediation_path or remediation_yaml:
        return ArtifactRole.REMEDIATION_EPISODE_RECEIPT

    genesis_match = _GENESIS_RECEIPT_PATH_RE.match(normalized)
    title_value = root.get("title")
    if (
        genesis_match
        and genesis_match.group(1) == package_id
        and isinstance(title_value, str)
        and title_value.strip()
        and (
            not isinstance(declared_package, str)
            or declared_package == package_id
        )
    ):
        return ArtifactRole.PACKAGE_GENESIS_RECEIPT

    # Explicit package+title YAML under docs/evidence without remediation
    # markers and without the governed genesis path shape → unknown (fail closed).
    return ArtifactRole.UNKNOWN
