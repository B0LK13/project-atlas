# ADR-004 — Source quarantine and prompt-injection boundary contract

**Status:** accepted for implementation
**Date:** 2026-08-03
**Work package:** AS-SEC-001
**Author:** Architecture Governor (entry-gate authorization)

## Context

Atlas Core's founding principle is "evidence, not authority": Layer A holds
raw imported source evidence, Layer B holds canonical OKF concepts derived
from it, and Layer C holds synthesized portfolio intelligence. Nothing in the
vault carries a subjective trust score, and every claim traces back to a
source.

That principle currently has no *enforced* boundary against adversarial
source content. Inspecting the certified ingestion path
(`src/project_atlas/ingestion.py`) and the current security posture
(`AGENTS.md` §Security considerations) shows:

- `project_atlas.secrets.scan_text` (`src/project_atlas/secrets.py`) excludes
  a source from ingestion when it matches a secret-shaped pattern (private
  key, bearer token, API key, password assignment, connection string, cloud
  access key), and records metadata-only findings to
  `generated/reports/secret-findings.json`. This is a **content-safety**
  control, not an **instruction-safety** control — it has no concept of
  prompt-injection or adversarial-instruction content, only credential-shaped
  strings.
- Legitimate source documents (`README.md`, `ARCHITECTURE.md`, etc.) have
  their full text copied byte-for-byte into
  `vault/sources/imported-documents/` and are also carried in-memory as the
  `text` field feeding classification (`_classify`) and, downstream, claim
  extraction (`knowledge_compiler.py`). There is no rule preventing
  instruction-shaped source text (e.g. "ignore previous instructions",
  fake `SYSTEM:`/role-override blocks, canary/exfiltration markers) from
  being classified as a legitimate claim and surfaced in Layer B/C generated
  content as if it were fact — which is exactly the point at which an agent
  later reading the vault could mistake quoted adversarial text for a live
  instruction.
- The only existing quarantine mechanisms are narrowly scoped: agent-event
  quarantine (`vault/quarantine/agent-events/index.json`, hash/identity/
  pipeline-state mismatches) and the Control Plane's own document quarantine
  (`atlas-vault-documentation/docs/THREAT_MODEL.md`). Atlas Core has no
  general-purpose source-document quarantine or written injection-boundary
  contract of its own.

This is a real, verified gap, not a hypothetical one: this repository's own
`secrets.py` patterns and this ADR's own prose both contain the string
"ignore" and instruction-shaped language, which is precisely the kind of
content a naive boundary could either over-quarantine or, worse, silently
let through into synthesized output.

## Decision

Establish **AS-SEC-001** as a bounded, deterministic, offline contract with
three parts:

1. **Generalized source quarantine.** Extend the existing per-source
   quarantine model (currently secret-scan-only) with a second, independent
   pattern class: adversarial-instruction detection. A source matching either
   class is excluded from classification/claim-extraction and recorded to a
   new `generated/reports/injection-findings.json` report (metadata only:
   source id, path, pattern name, confidence — never the matched text,
   mirroring `SecretFinding`'s existing discipline). Detection stays
   conservative, pattern-based, and stdlib/regex-only — no LLM classification,
   no network calls, no runtime sandboxing (this preserves NFR-xxx
   determinism and offline operation).
2. **Rendering/quoting boundary contract.** Any source text that *is*
   ingested (i.e., did not match either quarantine class) must be treated as
   quoted evidence, never as live instruction, anywhere it is echoed into
   generated content: Layer A raw copies continue as byte-identical evidence
   files (already true) but gain a frontmatter marker declaring them
   untrusted quoted evidence; any excerpt surfaced in Layer B/C generated
   Markdown (concept notes, navigation, reports) must be fenced or
   block-quoted, never interpolated as bare prose or as a heading/title.
   This is a **written contract document** (this ADR plus a follow-on
   reference doc), not a runtime sandbox — the existing deterministic
   rendering functions in `okf_renderer.py`/`semantic_compiler.py` are
   audited against it, and gaps are fixed as part of AS-SEC-001's
   implementation.
3. **Adversarial fixture corpus.** A `tests/fixtures/adversarial/` corpus of
   instruction-bearing documents, canary strings, and malformed/oversized/
   unicode-adversarial frontmatter, each with a paired failing-then-passing
   test, exercised in both the Core suite and (where applicable) the Control
   Plane suite.

### Non-scope (explicit)

- No LLM or external-provider features of any kind.
- No changes to the existing agent-event quarantine pipeline or its schemas.
- No changes to the existing secret-scan exclusion behavior beyond adding the
  second, independent pattern class alongside it.
- No runtime sandboxing, no execution of any kind of ingested content.
- No rewriting of `atlas-vault-documentation/`'s own, already-certified
  quarantine and threat-model surface — AS-SEC-001 covers Atlas Core's source
  ingestion boundary only. A future package may reconcile the two documents
  if a shared contract is judged necessary; that is out of scope here.
- No change to `src/`, `tests/`, or `schemas/` performed by this ADR itself —
  this is an entry-gate authorization, not an implementation.

### Acceptance criteria (binding on the implementation agent)

- Every new quarantine/quoting rule has a fixture that fails before the rule
  exists and passes after.
- No canary or instruction-marker string from a quarantined fixture appears
  anywhere under `vault/generated/` after a full pipeline run.
- No quarantined source is classified into a `ConceptRecord`/`Claim` by
  `knowledge_compiler.py`.
- Every non-quarantined source's text appears in generated Markdown only
  inside a fenced code block or blockquote — never as bare interpolated
  prose, a heading, or a title.
- Zero regression: full Core and Control Plane suites remain green; `ruff`
  and `mypy` remain clean.
- The existing certified pipeline (`discover → ingest → build-indexes →
  validate`) remains fully functional with no output-shape changes for
  non-adversarial input (byte-identical replay on the existing golden
  fixtures).

### Evidence requirements

- Security test report (adversarial fixture pass/fail matrix) + receipt,
  following this repository's existing evidence-commit convention
  (`docs/evidence/AS-SEC-001-receipt.yaml`).
- `WORKLOG.md` entry recording implementation scope, commands, and results.
- Independent Certifier adversarial review is mandatory before this package
  can be marked merge-eligible — this is the first security-classification
  surface added to Atlas Core, so self-certification by the implementer is
  not acceptable (separation of duties).
- Architecture Governor sign-off required before merge, given this is also
  the first contract that constrains *rendering* behavior across
  `okf_renderer.py`, `semantic_compiler.py`, and `knowledge_compiler.py`
  simultaneously — a cross-cutting surface, not a single-module change.

## Consequences

- Atlas Core gains a real, tested boundary between "evidence" and
  "instruction," closing a gap that existed in the certified pipeline since
  AS-CORE-002/003 without being explicitly named or tested.
- The detection patterns will need periodic extension (like `secrets.py`'s
  patterns already do) as new adversarial techniques are identified; this
  ADR does not attempt to be exhaustive, only to establish the contract,
  quarantine mechanics, and quoting discipline.
- `generated/reports/injection-findings.json` becomes a new, additive
  report artifact; it does not change any existing report's shape.
- No existing certified work package's semantics change: AS-RET-001's
  lexical index, the single promotion boundary, durable identity/lifecycle
  semantics, and Control Plane isolation are all unaffected by this ADR
  (verified: no `src/`, `tests/`, or `schemas/` change accompanies it).
