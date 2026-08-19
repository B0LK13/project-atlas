"""Trusted mda-cli output contract (AS-MDA-CONTROL-PLANE-COMPAT-001-R1).

Real mda-cli 0.2.9 writes basename-preserving sibling output:

    <source>.md  →  <source>.restructured.md

The Atlas adapter must derive that path from an explicit version contract.
It must not discover output by scanning for the newest sibling Markdown file,
must not treat ``*.normalized.md`` as production success, and must not assume
``.restructured.md`` for unrecognized future versions.

``*.normalized.md`` remains a legacy fixture / historical mock convention.
Scan helpers may still classify it as a normalized *artifact class* so raw-event
rules are not applied to leftover fixtures. Production success for a current
mda-cli 0.2.9 invocation requires the canonical restructured suffix.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CANONICAL_RESTRUCTURED = "CANONICAL_RESTRUCTURED"
RESTRUCTURED_SUFFIX = ".restructured.md"
LEGACY_FIXTURE_SUFFIX = ".normalized.md"
DIRECTORY_FLAG_0_2_9 = "--out-dir"
KNOWN_VERSION_ID = "0.2.9"

# Accept "mda 0.2.9", "mda-cli 0.2.9", "0.2.9", and the test fixture
# "mda 0.2.9-mock" which models the production 0.2.9 contract.
_KNOWN_VERSION_RE = re.compile(
    r"(?:^|[\s])(?:mda(?:-cli)?[\s]+)?(?P<ver>0\.2\.9)(?:-mock)?(?:\s|$)",
    re.IGNORECASE,
)
_ANY_VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+)\b")


class UnknownMdaContractError(ValueError):
    """Raised when the probed mda-cli version cannot be mapped safely."""


@dataclass(frozen=True)
class MdaOutputContract:
    """Explicit trusted mapping from a recognized mda-cli version to output."""

    version_id: str
    classification: str
    suffix: str
    directory_flag: str

    @property
    def is_canonical_restructured(self) -> bool:
        return self.classification == CANONICAL_RESTRUCTURED and self.suffix == RESTRUCTURED_SUFFIX


CONTRACT_0_2_9 = MdaOutputContract(
    version_id=KNOWN_VERSION_ID,
    classification=CANONICAL_RESTRUCTURED,
    suffix=RESTRUCTURED_SUFFIX,
    directory_flag=DIRECTORY_FLAG_0_2_9,
)


def parse_mda_version_id(version_line: str) -> str | None:
    """Return ``0.2.9`` when the probe line is a recognized 0.2.9 family string."""
    text = (version_line or "").strip().splitlines()[0] if version_line else ""
    if not text:
        return None
    known = _KNOWN_VERSION_RE.search(text)
    if known:
        return known.group("ver")
    return None


def resolve_output_contract(version_line: str) -> MdaOutputContract:
    """Map a probed ``--version`` line to a trusted output contract.

    Unrecognized versions fail closed. This function never defaults to
    ``.restructured.md`` for an unknown version family.
    """
    version_id = parse_mda_version_id(version_line)
    if version_id == KNOWN_VERSION_ID:
        return CONTRACT_0_2_9
    other = _ANY_VERSION_RE.search((version_line or "").strip())
    detail = other.group(1) if other else (version_line or "unknown")
    raise UnknownMdaContractError(
        f"unrecognized mda-cli version contract: {detail!r}"
    )


def is_mda_output_artifact(name: str) -> bool:
    """True for current-run contract output or leftover legacy fixture names.

    Used by scanners so ``*.restructured.md`` and historical ``*.normalized.md``
    are not validated as raw events. Production success still requires the
    canonical restructured suffix for mda-cli 0.2.9.
    """
    return name.endswith(RESTRUCTURED_SUFFIX) or name.endswith(LEGACY_FIXTURE_SUFFIX)


def raw_sibling_for(normalized_path: Path) -> Path | None:
    """Map a normalized artifact name back to ``<stem>.md`` if the suffix is known."""
    name = normalized_path.name
    for suffix in (RESTRUCTURED_SUFFIX, LEGACY_FIXTURE_SUFFIX):
        if name.endswith(suffix):
            return normalized_path.with_name(name[: -len(suffix)] + ".md")
    return None


def output_filename(raw_event: Path, contract: MdaOutputContract) -> str:
    """Basename-preserving output filename for ``raw_event`` under ``contract``."""
    name = raw_event.name
    stem = name[: -len(".md")] if name.endswith(".md") else name
    return stem + contract.suffix


def expected_output_path(
    raw_event: Path,
    contract: MdaOutputContract,
    *,
    output_mode: str,
    output_dir: Path | None,
) -> Path:
    """Deterministic expected output path. Never scans the directory."""
    filename = output_filename(raw_event, contract)
    if output_mode == "sibling":
        return raw_event.parent / filename
    if output_mode != "directory":
        raise ValueError(f"invalid output_mode: {output_mode!r}")
    if output_dir is None:
        raise ValueError("output_mode 'directory' requires output_dir")
    return output_dir / filename
