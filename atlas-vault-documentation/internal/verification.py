"""Verification of untrusted normalization output (AS-WP-002, Priority 3).

mda-cli exiting zero is never sufficient. Every produced document is
verified before it is accepted: existence, uniqueness, location,
readability, frontmatter, linkage to the originating raw event, secret
absence, and absence of unexpected side-effect files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from internal import provenance

# Reuse the secret patterns from the validation script's taxonomy. The
# patterns are duplicated deliberately (scripts must stay standalone);
# keep the two lists in sync with scripts/check_documentation.py.
SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", re.I),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}", re.I),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
]

REQUIRED_TYPE = "Agent Work Event"


@dataclass(frozen=True)
class VerificationResult:
    """Structured verification outcome; ``problems`` empty means verified."""

    output_path: Path
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def verified(self) -> bool:
        return not self.problems


def snapshot(directory: Path) -> frozenset[Path]:
    """All files directly and transitively inside ``directory`` (if any)."""
    if not directory.is_dir():
        return frozenset()
    return frozenset(path for path in directory.rglob("*") if path.is_file())


def ensure_inside_root(root: Path, candidate: Path) -> None:
    """Fail closed when ``candidate`` resolves outside ``root``."""
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            f"unsafe output path outside root: {resolved_candidate}"
        ) from exc


def verify_output(
    output_path: Path,
    *,
    root: Path,
    raw_event_id: str,
    watch_directory: Path,
    before: Iterable[Path],
) -> VerificationResult:
    """Verify one normalization output against every acceptance rule.

    - the expected output exists and is readable;
    - it resolves inside ``root``;
    - no unexpected new files appeared in ``watch_directory``;
    - frontmatter declares ``type: Agent Work Event``;
    - the document references the raw event ID (identity and source);
    - no secret-shaped content is present.
    """
    problems: list[str] = []

    try:
        ensure_inside_root(root, output_path)
    except ValueError as exc:
        problems.append(str(exc))

    if not output_path.is_file():
        problems.append(f"expected output missing: {output_path}")
        text = None
    else:
        try:
            text = output_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            problems.append(f"output unreadable: {type(exc).__name__}")
            text = None

    after = snapshot(watch_directory)
    new_files = after - frozenset(before)
    unexpected = sorted(
        path
        for path in new_files
        if path != output_path and path != output_path.resolve()
    )
    for extra in unexpected:
        problems.append(f"unexpected file produced: {extra}")

    if text is not None:
        try:
            frontmatter, _ = provenance.split_document(text)
        except ValueError as exc:
            problems.append(str(exc))
        else:
            if f"type: {REQUIRED_TYPE}" not in frontmatter:
                problems.append("frontmatter type is not 'Agent Work Event'")
        if f"agent-event:{raw_event_id}" not in text:
            problems.append("output does not reference the raw event ID")
        if f"source:agent-event:{raw_event_id}" not in text:
            problems.append("output lacks raw source provenance reference")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            problems.append("likely secret detected in normalized output")

    return VerificationResult(output_path=output_path, problems=tuple(problems))
