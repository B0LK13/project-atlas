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

# Explicit confusable-character mapping for visual homoglyphs that evade
# simple Latin-only keyword matching. The list is intentionally bounded to
# characters that are visually identical (or near-identical) to Latin letters
# used in the adversarial-instruction keyword set. It is a static, bundled,
# offline table — no network fetch or ML similarity scoring.
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
    "\u04cf": "I",  # CYRILLIC SMALL LETTER PALOCHKA -> Latin capital I
    # Cyrillic capital letters that visually match Latin counterparts.
    "\u0410": "A",  # CYRILLIC CAPITAL LETTER A
    "\u0415": "E",  # CYRILLIC CAPITAL LETTER IE
    "\u0406": "I",  # CYRILLIC CAPITAL LETTER BYELORUSSIAN-UKRAINIAN I
    "\u0408": "J",  # CYRILLIC CAPITAL LETTER JE
    "\u041e": "O",  # CYRILLIC CAPITAL LETTER O
    "\u0420": "P",  # CYRILLIC CAPITAL LETTER ER
    "\u0421": "C",  # CYRILLIC CAPITAL LETTER ES
    "\u0422": "T",  # CYRILLIC CAPITAL LETTER TE
    "\u0425": "X",  # CYRILLIC CAPITAL LETTER HA
    "\u042b": "Y",  # CYRILLIC CAPITAL LETTER YERU
    "\u0474": "Y",  # CYRILLIC CAPITAL LETTER IZHITSA
    # Greek letters that visually match Latin counterparts.
    "\u0391": "A",  # GREEK CAPITAL LETTER ALPHA
    "\u0392": "B",  # GREEK CAPITAL LETTER BETA
    "\u0395": "E",  # GREEK CAPITAL LETTER EPSILON
    "\u0397": "H",  # GREEK CAPITAL LETTER ETA
    "\u0399": "I",  # GREEK CAPITAL LETTER IOTA
    "\u039a": "K",  # GREEK CAPITAL LETTER KAPPA
    "\u039c": "M",  # GREEK CAPITAL LETTER MU
    "\u039d": "N",  # GREEK CAPITAL LETTER NU
    "\u039f": "O",  # GREEK CAPITAL LETTER OMICRON
    "\u03a1": "P",  # GREEK CAPITAL LETTER RHO
    "\u03a4": "T",  # GREEK CAPITAL LETTER TAU
    "\u03a7": "X",  # GREEK CAPITAL LETTER CHI
    "\u0396": "Z",  # GREEK CAPITAL LETTER ZETA
    "\u03b1": "a",  # GREEK SMALL LETTER ALPHA
    "\u03b2": "b",  # GREEK SMALL LETTER BETA
    "\u03b5": "e",  # GREEK SMALL LETTER EPSILON
    "\u03b7": "h",  # GREEK SMALL LETTER ETA
    "\u03b9": "i",  # GREEK SMALL LETTER IOTA
    "\u03ba": "k",  # GREEK SMALL LETTER KAPPA
    "\u03bc": "m",  # GREEK SMALL LETTER MU
    "\u03bd": "n",  # GREEK SMALL LETTER NU
    "\u03bf": "o",  # GREEK SMALL LETTER OMICRON
    "\u03c1": "p",  # GREEK SMALL LETTER RHO
    "\u03c4": "t",  # GREEK SMALL LETTER TAU
    "\u03c7": "x",  # GREEK SMALL LETTER CHI
    "\u03b6": "z",  # GREEK SMALL LETTER ZETA
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

    1. NFKD compatibility decomposition so accented letters are represented
       as their base character plus combining marks.
    2. Remove format-control characters (category ``Cf``) and combining marks
       (category ``Mn``), including zero-width spaces/joiners, soft hyphens,
       directional isolates, and diacritical marks that can be used to evade
       regex word-boundary or token matching.
    3. Handle C0/C1 control characters (category ``Cc``):

       - Keep tab, line feed, and carriage return as ASCII whitespace so that
         normal line boundaries still delimit words.
       - Remove every other control character (including vertical tab, form
         feed, null, backspace, bell, escape, and other C0/C1 controls) so
         that control characters injected mid-keyword collapse back into the
         keyword.
    4. Normalize every Unicode separator (general category ``Z``: Zs, Zl, Zp)
       to a single ASCII space. All Z-category characters are separators by
       definition, so there is no legitimate reason to preserve distinctions
       between them for keyword matching. This prevents mid-keyword injection
       via em space, no-break space, line separator, paragraph separator, etc.
    5. Apply the narrow explicit confusable-character mapping so that
       visually identical Cyrillic/Greek homoglyphs are treated as their Latin
       look-alikes during pattern matching.

    The original source bytes are never modified; this normalization is used
    only inside the detector.
    """
    normalized = unicodedata.normalize("NFKD", text)
    stripped: list[str] = []
    for ch in normalized:
        category = unicodedata.category(ch)
        if category in {"Cf", "Mn"}:
            continue
        if category == "Cc":
            if ch in {"\t", "\n", "\r"}:
                stripped.append(" ")
            continue
        if category.startswith("Z"):
            stripped.append(" ")
            continue
        stripped.append(ch)
    mapped = "".join(_CONFUSABLE.get(ch, ch) for ch in stripped)
    return mapped


def scan_text(text: str) -> list[InjectionFinding]:
    """Return metadata-only adversarial-instruction findings for ``text``.

    Findings are deterministic and ordered by rule name to keep reports
    stable across runs. The matched content is never returned.
    """
    normalized = _normalize_detector_input(text)
    findings: list[InjectionFinding] = []
    seen: set[str] = set()
    for rule, confidence, hint, pattern in _PATTERNS:
        if pattern.search(normalized) and rule not in seen:
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
