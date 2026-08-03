"""Deterministic, offline adversarial-instruction detection for source ingestion.

AS-SEC-001 extends the existing secret-scan quarantine with a second,
independent pattern class: instruction-bearing or agent-mimicking content
that must not reach claim extraction or generated instructions. Detection is
regex-based, stdlib-only, deterministic, and returns metadata-only findings
never containing the matched payload.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


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


def scan_text(text: str) -> list[InjectionFinding]:
    """Return metadata-only adversarial-instruction findings for ``text``.

    Findings are deterministic and ordered by rule name to keep reports
    stable across runs. The matched content is never returned.
    """
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
