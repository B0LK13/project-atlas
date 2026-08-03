"""Deterministic, offline adversarial-instruction detection for source ingestion.

AS-SEC-001 extends the existing secret-scan quarantine with a second,
independent pattern class: instruction-bearing or agent-mimicking content
that must not reach claim extraction or generated instructions. Detection is
regex-based, stdlib-only, deterministic, and returns metadata-only findings
never containing the matched payload.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Narrow explicit confusable-character mapping for visual homoglyphs that
# evade simple Latin-only keyword matching (e.g., Cyrillic look-alikes). This is
# intentionally conservative: only demonstrated near-identical letters are
# mapped, not every Unicode homoglyph.
_CONFUSABLE: dict[str, str] = {
    # Cyrillic small letters that visually match Latin counterparts.
    "\u0430": "a",  # CYRILLIC SMALL LETTER A
    "\u0435": "e",  # CYRILLIC SMALL LETTER IE
    "\u0456": "i",  # CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
    "\u0458": "j",  # CYRILLIC SMALL LETTER JE
    "\u043e": "o",  # CYRILLIC SMALL LETTER O
    "\u0440": "p",  # CYRILLIC SMALL LETTER ER
    "\u0441": "c",  # CYRILLIC SMALL LETTER ES
    "\u0442": "t",  # CYRILLIC SMALL LETTER TE
    "\u0445": "x",  # CYRILLIC SMALL LETTER HA
    "\u044b": "y",  # CYRILLIC SMALL LETTER YERU
    "\u0475": "y",  # CYRILLIC SMALL LETTER IZHITSA
    "\u04cf": "\u0049",  # CYRILLIC SMALL LETTER PALOCHKA -> Latin capital I
}


@dataclass(frozen=True)
class InjectionFinding:
    """Metadata-only finding for adversarial source content.

    The finding deliberately excludes the matched text so malicious payloads
    are not carried into reports, logs, or generated content.
    """

    rule: str
    pattern: str
    confidence: str
    redacted_hint: str


# Confidence taxonomy mirrors secrets.py for consistency:
#   high   - explicit instruction override or agent-mimicry directive
#   medium - role/permission framing that could act as a directive
_PATTERNS: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    (
        "instruction-override",
        "high",
        "explicit override of previous instructions",
        re.compile(
            r"(?i)\b(?:ignore|disregard|forget|override|bypass)\s+"
            r"(?:all\s+|any\s+|the\s+|those\s+|previous\s+|prior\s+|earlier\s+|above\s+|foregoing\s+)*"
            r"(?:instructions|rules|directives|constraints|prompts)\b"
        ),
    ),
    (
        "authority-grant",
        "high",
        "statement that grants new permissions to the reader",
        re.compile(
            r"(?i)\b(?:you\s+are\s+now\s+|you\s+have\s+been\s+)?"
            r"(?:allowed|permitted|authorized|required|instructed|empowered)\s+to\s+"
            r"(?:ignore|disregard|override|bypass|skip|drop|remove|change|reveal|share|send)"
        ),
    ),
    (
        "binding-rewriting",
        "high",
        "text promoted as authoritative or binding",
        re.compile(
            r"(?i)\btreat\s+(?:the\s+following|this|below|what\s+follows)\s+"
            r"(?:text|content|instruction|directive)s?\s+as\s+"
            r"(?:authoritative|binding|canonical|true|trusted|overriding|superseding)"
        ),
    ),
    (
        "agent-directive-mimicry",
        "high",
        "marker that mimics an agent control directive",
        re.compile(
            r"(?i)\b(?:NEXT_AGENT_DIRECTIVE|NEXT\s+PHASE\s*[:=]|"
            r"system\s+prompt\s*[:=]|user\s+prompt\s*[:=]|"
            r"developer\s+message\s*[:=]|admin\s+directive\s*[:=])"
        ),
    ),
    (
        "role-override",
        "medium",
        "role or mode override framing",
        re.compile(
            r"(?i)\b(?:simulate|pretend|roleplay|act\s+as|you\s+are\s+now)\s+"
            r"(?:an?\s+)?(?:unrestricted|liberated|developer|admin|root|system|"
            r"superuser|privileged|enabled)\b"
        ),
    ),
    (
        "jailbreak-cue",
        "high",
        "known jailbreak or ignore-safety framing",
        re.compile(
            r"(?i)\b(?:DAN\s+mode|do\s+anything\s+now|jailbreak|"
            r"ignore\s+(?:your\s+)?(?:safety|ethical|policy|guideline|restriction)s?|"
            r"no\s+limits\s+mode)\b"
        ),
    ),
    (
        "system-role-override",
        "medium",
        "claim of system/developer/root role or override",
        re.compile(
            r"(?i)\b(?:system|developer|admin|root)\s+"
            r"(?:override|mode|prompt|role|instruction|directive)\b"
        ),
    ),
    (
        "new-rules-declaration",
        "high",
        "declaration of replacement rules or directives",
        re.compile(
            r"(?i)\bnew\s+(?:permanent\s+)?(?:instructions|rules|directives|constraints|"
            r"system\s+prompt)s?\s*[:;]"
        ),
    ),
    (
        "obligation-to-ignore",
        "high",
        "imperative telling the reader to ignore or override prior output",
        re.compile(
            r"(?i)\byou\s+(?:must|should|shall|need\s+to)\s+"
            r"(?:ignore|disregard|override|bypass|forget|remove|drop)"
            r"(?:\s+(?:all|any|the|those|previous|prior|earlier|above|foregoing))?"
            r"(?:\s+(?:instructions|rules|directives|constraints|prompts|output|responses?))?"
        ),
    ),
)


def _normalize_detector_input(text: str) -> str:
    """Prepare raw Unicode text for deterministic adversarial-instruction scanning.

    Steps, in order:

    1. NFKC compatibility decomposition/recomposition so that visually
       equivalent compatibility characters collapse to canonical forms.
    2. Remove Unicode format-control characters (category ``Cf``), including
       zero-width spaces/joiners, soft hyphens, and directional isolates that
       can be used to evade regex word-boundary or token matching.
    3. Apply the narrow explicit confusable-character mapping so that
       visually identical Cyrillic homoglyphs are treated as their Latin
       look-alikes during pattern matching.

    The original source bytes are never modified; this normalization is used
    only inside the detector.
    """
    normalized = unicodedata.normalize("NFKC", text)
    without_format_controls = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Cf"
    )
    mapped = "".join(_CONFUSABLE.get(ch, ch) for ch in without_format_controls)
    return mapped


def scan_text(text: str) -> list[InjectionFinding]:
    """Return metadata-only adversarial-instruction findings for ``text``.

    Findings are deterministic and ordered by rule name to keep reports
    stable across runs. The matched content is never returned.
    """
    text = _normalize_detector_input(text)
    findings: list[InjectionFinding] = []
    seen: set[str] = set()
    for rule, confidence, hint, pattern in _PATTERNS:
        if pattern.search(text) and rule not in seen:
            findings.append(
                InjectionFinding(
                    rule=rule,
                    pattern=rule,
                    confidence=confidence,
                    redacted_hint=hint,
                )
            )
            seen.add(rule)
    return sorted(findings, key=lambda finding: finding.rule)


def scan_identifier(value: str) -> list[InjectionFinding]:
    """Scan a structural identifier for adversarial-instruction content.

    Project IDs, directory names, and citation keys often join words with
    hyphens, underscores, or slashes rather than spaces. This helper
    normalizes those separators before applying the same pattern set as
    ``scan_text`` so that ``ignore-previous-instructions`` is treated the same
    as ``ignore previous instructions``.
    """
    normalized = value.replace("-", " ").replace("_", " ").replace("/", " ")
    return scan_text(normalized)
