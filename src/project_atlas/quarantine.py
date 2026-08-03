"""Deterministic, offline adversarial-instruction detection for source ingestion.

AS-SEC-001 extends the existing secret-scan quarantine with a second,
independent pattern class: instruction-bearing or agent-mimicking content
that must not reach claim extraction or generated instructions. Detection is
regex-based, stdlib-only, deterministic, and returns metadata-only findings
never containing the matched payload.
"""

from __future__ import annotations

import re
import sys
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


def _z_category_characters() -> frozenset[str]:
    """Return every Unicode Zs/Zl/Zp character known to the running interpreter.

    AS-SEC-001-GOV-006 residual remediation: computed once from
    ``unicodedata.category`` against the full codepoint range rather than a
    hand-maintained literal list, so this automatically tracks whatever
    Unicode version the running Python interpreter ships with instead of
    silently going stale as new separator characters are added upstream.
    """
    return frozenset(
        chr(codepoint)
        for codepoint in range(sys.maxunicode + 1)
        if unicodedata.category(chr(codepoint)) in {"Zs", "Zl", "Zp"}
    )


_Z_CATEGORY_CHARACTERS: frozenset[str] = _z_category_characters()

# The plain keyboard space (U+0020, category Zs) is deliberately excluded
# from the ambiguous-separator run/variant mechanism below. It is category
# Zs like the other 18 characters, but unlike them it is the single,
# near-universal word separator throughout ordinary prose: a real sentence
# has an isolated single occurrence of it between *every* pair of words, not
# occasionally like an em space or a line separator. Variant B's "remove an
# isolated single occurrence" rule cannot distinguish the one occurrence an
# attacker spliced into a keyword from the dozens of legitimate occurrences
# elsewhere in the same text (per-character local context alone cannot tell
# them apart, by design - see ``scan_text``), so applying it to U+0020 would
# strip every space in the document and make Variant B unable to match any
# multi-word pattern at all, including ones with no adversarial intent.
# Splitting a keyword with a literal space also yields two ordinary-looking
# word fragments rather than an invisible/exotic Unicode trick, so closing
# that specific case is a different problem (arbitrary fuzzy/edit-distance
# keyword matching) explicitly out of ADR-004's bounded, deterministic scope
# - not a Unicode-category evasion this remediation is meant to close. This
# boundary is deliberate and documented, not a silently dropped case: see
# ``test_ascii_space_mid_keyword_split_is_not_a_unicode_evasion_bypass`` and
# the AS-SEC-001-GOV-006 residual evidence.
_REMOVABLE_Z_CATEGORY_CHARACTERS: frozenset[str] = _Z_CATEGORY_CHARACTERS - {" "}

# Characters whose *run length* is ambiguous for keyword-boundary purposes:
# tab/line-feed/carriage-return (AS-SEC-001-GOV-007) plus every Unicode
# separator other than plain space (Zs/Zl/Zp minus U+0020 — AS-SEC-001-
# GOV-006 residual). All of them share the same structural property: a lone
# occurrence is, in isolation, indistinguishable between "ordinary word/line
# separator" and "single character mid-keyword evasion", while a run of two
# or more of them is an unambiguous, intentional boundary (a blank line, a
# deliberately wide inter-word gap, a paragraph break, ...). ``scan_text``
# below applies one shared, bounded, run-length-aware dual-variant scan to
# this whole set rather than a second parallel normalization pipeline.
_AMBIGUOUS_SEPARATOR_CHARACTERS: frozenset[str] = (
    frozenset({"\t", "\n", "\r"}) | _REMOVABLE_Z_CATEGORY_CHARACTERS
)

_AMBIGUOUS_SEPARATOR_RUN = re.compile(
    "(?:"
    + "|".join(re.escape(ch) for ch in sorted(_AMBIGUOUS_SEPARATOR_CHARACTERS))
    + ")+"
)


def _normalize_detector_input(text: str) -> str:
    """Strip format/combining marks and non-boundary control characters.

    Steps, in order:

    1. For every character in the *original* text, check its Unicode
       category first. A character already in category Zs, Zl, or Zp is
       kept as-is, unexpanded — NFKD compatibility decomposition maps most
       Zs characters (em space, no-break space, ideographic space, and
       every other fixed-width space variant except U+1680 OGHAM SPACE
       MARK) to a plain ASCII space, which would silently destroy the
       separator's original identity before the bounded ambiguous-separator
       handling in ``scan_text`` ever gets a chance to see it (three
       Zs/Zl/Zp characters — OGHAM SPACE MARK, LINE SEPARATOR, PARAGRAPH
       SEPARATOR — have no NFKD decomposition at all, so this also keeps
       every Z-category character's treatment uniform instead of splitting
       it by an accident of which ones happen to decompose).
    2. Every other character is NFKD-decomposed individually so accented
       letters are represented as their base character plus combining
       marks; this is a no-op for characters with no decomposition (e.g.
       control characters).
    3. From that per-character decomposition, remove format-control
       characters (category ``Cf``) and combining marks (category ``Mn``),
       including zero-width spaces/joiners, soft hyphens, directional
       isolates, and diacritical marks that can be used to evade regex
       word-boundary or token matching.
    4. Remove every C0/C1 control character other than tab, line feed, and
       carriage return (vertical tab, form feed, null, backspace, bell,
       escape, and the rest), so control characters injected mid-keyword
       collapse back into the keyword. Tab/line feed/carriage return and
       every Unicode separator (category ``Z``: Zs, Zl, Zp) are deliberately
       left untouched here — ``scan_text`` resolves all of them afterward as
       one shared, bounded, ambiguous-separator class, since how to treat
       any of them depends on whether they appear alone or as part of a run
       (see ``scan_text``).
    5. Apply the narrow explicit confusable-character mapping so that
       visually identical Cyrillic/Greek homoglyphs are treated as their Latin
       look-alikes during pattern matching.

    The original source bytes are never modified; this normalization is used
    only inside the detector.
    """
    kept: list[str] = []
    for ch in text:
        if unicodedata.category(ch) in {"Zs", "Zl", "Zp"}:
            kept.append(ch)
            continue
        for decomposed in unicodedata.normalize("NFKD", ch):
            category = unicodedata.category(decomposed)
            if category in {"Cf", "Mn"}:
                continue
            if category == "Cc" and decomposed not in {"\t", "\n", "\r"}:
                continue
            kept.append(decomposed)
    return "".join(_CONFUSABLE.get(ch, ch) for ch in kept)


def scan_text(text: str) -> list[InjectionFinding]:
    """Return metadata-only adversarial-instruction findings for ``text``.

    Tab, line feed, carriage return, and every Unicode separator (category
    ``Z``: Zs, Zl, Zp) are ambiguous: the same character can be a legitimate
    word boundary ("Ignore<EM SPACE>previous<EM SPACE>instructions", three
    real words) or an evasive insertion splitting one keyword in half
    ("Ign<EM SPACE>ore", one word). Neither "always treat as whitespace" nor
    "always remove" alone satisfies both cases: the first misses the
    split-keyword evasion; the second can glue an unrelated preceding or
    following word directly onto a keyword and defeat its ``\\b`` boundary
    (e.g. a heading ending in a bare word, immediately followed by a
    paragraph that starts with "Ignore"). Removing *every* occurrence
    document-wide is too broad; per-character local context alone cannot
    tell "mid-word" from "between words" (both look like letter-separator-
    letter).

    The run length is the deterministic signal used instead: a run of two or
    more consecutive characters from the combined ambiguous-separator set
    (tab/line-feed/carriage-return and/or Zs/Zl/Zp, in any combination) is a
    strong, unambiguous signal of an intentional paragraph/section break or
    a deliberately wide inter-word gap, and always collapses to a single
    space, in both variants below. A lone, isolated single occurrence is the
    ambiguous case — it could be ordinary single-character word spacing, or
    a one-character mid-keyword injection — so it is tested both ways:

    - Variant A: every run (including isolated single occurrences) becomes
      one ASCII space, preserving ordinary word/line/tab-separated
      boundaries (this is what catches a legitimate multi-word instruction
      that happens to use tab/newline/Z-category separators as its
      separator).
    - Variant B: runs of two or more still collapse to one space, but an
      isolated single occurrence is removed entirely, reuniting a keyword
      split by exactly one stray ambiguous-separator character without
      touching any genuine paragraph break or wide gap elsewhere in the
      text.

    The detector reports the union of findings from both variants.
    Findings are deterministic and ordered by rule name to keep reports
    stable across runs. The matched content is never returned.
    """
    prepared = _normalize_detector_input(text)
    variant_a = _AMBIGUOUS_SEPARATOR_RUN.sub(" ", prepared)
    variant_b = _AMBIGUOUS_SEPARATOR_RUN.sub(
        lambda match: " " if len(match.group(0)) > 1 else "", prepared
    )

    findings: list[InjectionFinding] = []
    seen: set[str] = set()
    for normalized in (variant_a, variant_b):
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
