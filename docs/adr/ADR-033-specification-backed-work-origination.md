# ADR-033 — Specification-Backed Work Origination (Phase 2A)

Status: proposed, pre-implementation. Authorized scope:
`SPECIFICATION_BACKED_WORK_ORIGINATION` only, per owner directive
`D-PHASE2A-SPECIFICATION-BACKED-WORK-ORIGINATION`. Does not authorize
general "what should I build next" reasoning, bug discovery without a
spec, or AI-invented product work (explicitly deferred, see §7).

## CURRENT_PIPELINE

Two independent, already-shipped pipelines exist and are not currently
connected:

1. **Knowledge extraction** (`ingest` → `knowledge_compiler.py`):
   deterministic claim extraction already produces typed, provenanced
   `Claim` objects (`domain/claims.py`) including
   `ClaimType.ROADMAP_STATUS`, `WORK_PACKAGE_STATUS`, `TEST_RESULT`,
   `DECISION`, `RISK` — each with `provenance: list[ProvenanceReference]`
   (`resource`, `locator`, `receipt_id`) tracing back to the exact
   source document/line. This is real, durable, already-ingested
   project evidence, not something this ADR needs to build.
2. **Roadmap lens** (`project_roadmap.py`, `AS-PROJECT-ROADMAP-001`):
   `build_roadmap_lens(vault, project_id)` computes `you_are_here`,
   `next_unlock`, critical path, etc. — but only from a structured
   `## Roadmap record` fenced JSON block it finds at
   `projects/<id>/roadmap.md` or, failing that, verbatim inside the
   compiled `project.md` (`_load_roadmap_source()`). **It never reads
   the claims from (1).** If no fenced record exists (the normal case
   for any real project that hasn't hand-authored one), `next_unlock`
   is always `UNKNOWN`/`no_roadmap_items` — this is exactly the
   `GAMMA_NEXT_WORK` gap, confirmed general, not Gamma-specific.

Separately, the autonomy/DAG side (`orchestration/autonomy/discovery.py`)
has its own, unrelated `discover()` — a **closed, hardcoded enumeration**
of six named historical packages belonging to the orchestration
subsystem's own development (`AS-ORCH-001D-R2/R7/R6`, `AS-ORCH-001E`, the
pilot, `AS-ORCH-001D` itself). It has no path from project content at
all and is out of scope to replace — Phase 2A adds a **second candidate
source** the governor can consult, it does not touch this enumeration.

## MISSING_ADAPTER_BOUNDARY

Nothing today reads (1)'s claims, applies the origination policy (§ below),
and writes (2)'s expected fenced record. That is the entire gap. Both
sides of the boundary already exist and are correct; only the
policy-gated bridge between them is missing.

```
Claims (ROADMAP_STATUS, WORK_PACKAGE_STATUS, TEST_RESULT, DECISION, RISK)
    -> origination.extract_candidate_facts()      [NEW, read-only]
    -> origination.correlate_evidence()            [NEW, deterministic]
    -> origination.build_proposal()                 [NEW, produces OriginationProposal]
    -> origination.validate_policy()                 [NEW, evidence quorum + negative checks]
    -> (if VALID) project_roadmap fenced-record writer  [NEW, writes projects/<id>/roadmap.md]
    -> build_roadmap_lens()                           [EXISTING, unmodified]
    -> next_unlock                                     [EXISTING, unmodified]
    -> (Phase 2A-2, separate PR) governor candidate adapter reading next_unlock
       -> WorkNode(risk_tier=O1, ...)                 [NEW, separate slice]
```

## PROPOSED_FACT/PROPOSAL SCHEMA

New module `src/project_atlas/orchestration/origination.py` (autonomy-
adjacent but not under `autonomy/` — it depends on `domain`/vault claims,
which `autonomy/` currently does not import, and should stay a one-way
dependency: origination reads the vault, autonomy reads origination's
*output* (the roadmap projection), never the vault claims directly).

```python
class EvidenceSignal(BaseModel):
    """One claim used as intent or corroborating evidence."""
    model_config = ConfigDict(extra="forbid")
    claim_id: str
    claim_type: ClaimType
    signal_role: Literal["authoritative_intent", "corroborating_acceptance"]
    resource: str            # from Claim.provenance[0].resource
    locator: str | None
    value: str                # the claim's own value, for human review

class OriginationProposal(BaseModel):
    """Never a command, never executable on its own -- mirrors
    NextActionCandidate's authority discipline (intelligence/next_action.py)."""
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORIGIN-001"] = "AS-ORIGIN-001"
    work_id: str               # deterministic hash of (project_id, subject, authoritative claim_id)
    project_id: str
    title: str
    why_this_work: str
    source_evidence: tuple[EvidenceSignal, ...]   # >= 2, >= 1 of each role
    source_locations: tuple[str, ...]
    proposed_scope: tuple[str, ...]                # paths/areas implied by evidence, not invented
    success_criteria: tuple[str, ...]              # from named tests/acceptance clauses only
    dependencies: tuple[str, ...]
    contradictions: tuple[str, ...]                # non-empty => BLOCKED
    risk_class: Literal["O1"] = "O1"               # Phase 2A only ever proposes O1
    authority_class: Literal["EXECUTION_READY", "OWNER_HELD"]
    confidence: Literal["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]
    status: Literal["VALID", "BLOCKED", "INSUFFICIENT_ACCEPTANCE_CONTRACT"]
    block_reason: str | None = None
    is_command: Literal[False] = False
    executable: Literal[False] = False
```

`work_id` is a deterministic hash (matching `next_action.py`'s
`_candidate()` pattern) so re-running origination against unchanged
evidence produces the *same* id — required for `NO_DUPLICATE_ORIGINATION`
and `STABLE_WORK_IDENTITY` (§10 negative requirements).

## POLICY GATE

`validate_policy(candidate_facts) -> OriginationProposal`, pure and
deterministic (no LLM call decides pass/fail — only extraction may use
model assistance, and Phase 2A's first adapter targets **structured
claims already produced by the deterministic knowledge compiler**, so
no model call is even needed for v1):

1. Require >= 1 `authoritative_intent` signal: a `ROADMAP_STATUS` or
   `WORK_PACKAGE_STATUS` claim whose normalized value indicates
   next/ready/planned (reuse `project_roadmap._normalize_status`'s
   existing vocabulary rather than inventing a second one).
2. Require >= 1 `corroborating_acceptance` signal: a `TEST_RESULT` claim
   for a skipped/xfail/not-yet-passing test, or a second independent
   `WORK_PACKAGE_STATUS`/`DECISION` claim citing concrete acceptance
   criteria — never the same claim counted twice.
3. Reject if any contradicting claim exists for the same subject
   (reuse the existing conflict-detection machinery in
   `knowledge_compiler.py`/`domain/conflicts.py` rather than a new
   contradiction detector) -> `status=BLOCKED`,
   `block_reason=CONFLICTING_PROJECT_EVIDENCE`.
4. Reject already-`IMPLEMENTED`/`VERIFIED_COMPLETION` work package status
   claims, superseded claims (`ClaimLifecycle`), and claims whose
   `authority` is below a floor (no `INFERRED`-only intent signal).
5. If success criteria can't be derived from a named test or explicit
   acceptance clause -> `status=VALID` but
   `authority_class` stays whatever §1-4 computed while
   `confidence=EVIDENCE_PARTIAL` and a separate
   `EXECUTION_READY=NO / INSUFFICIENT_ACCEPTANCE_CONTRACT` flag is set —
   origination succeeds, execution readiness does not (directive §6).
6. Compute `proposed_scope` only from evidence `resource`/mutation-surface
   hints already present in the claims (e.g. a `WORK_PACKAGE_STATUS`
   claim's own subject path) — never inferred beyond what's cited.
7. `risk_class` is always `O1` in Phase 2A (single tier); `authority_class`
   is `OWNER_HELD` if the proposed scope, once known, would touch any
   directive-§5 excluded surface (CI/workflow files, auth/security
   modules, dependency manifests unless the evidence itself specifies a
   dependency change, migrations, deploy config) — a static path/file
   classifier, not model judgment, per directive §7.

## INTEGRATION WITH EXISTING ROADMAP_UNLOCK

A `VALID` proposal is projected into exactly the fenced-JSON shape
`_parse_fenced_record`/`_load_roadmap_source` already parse (same
`roadmap_items[].{id,status,lifecycle,depends_on,evidence,notes}` shape
project_roadmap.py defines) and written to `projects/<id>/roadmap.md`
via the existing `_write_atomic` atomic-write convention. `build_roadmap_lens`
and everything downstream of it (`next_unlock`, CLI `atlas roadmap`,
`atlas next`) is **not modified** — it will simply start finding a real
record where today it finds none, which is the whole point.

## FAIL-CLOSED PATHS

- No evidence quorum met -> no record written, no candidate exists
  (silent-safe, not an error — most projects have no such work today).
- Contradicting evidence -> `BLOCKED`, recorded with reason, no record
  written.
- Already-implemented/superseded work -> filtered before quorum check,
  never proposed.
- Cross-project evidence -> `project_id` is carried on every `Claim` and
  `EvidenceSignal`; correlation only ever groups claims sharing the same
  `project_id` — enforced by construction (a dict keyed by `project_id`,
  not a filter that can be bypassed).
- Prompt-injection-shaped content inside a claim's `value` (directive
  §10 "malicious/instruction-like prose") — this pipeline never sends
  claim text to a model for a *decision*; policy is pure Python over
  structured fields. Instruction-like prose can at most become inert
  `title`/`why_this_work` string content in a proposal that a human or
  the O1 executor later reads, same trust boundary the rest of Atlas
  already applies to any vault content (`MODEL OUTPUT != AUTHORITY`).
- Write failure / partial write -> same `_write_atomic` temp-file +
  `os.replace` atomicity the rest of the codebase relies on; no partial
  fenced record can ever be read back.

## Phasing (per directive §9 — adapter certified before end-to-end demo)

- **Phase 2A-1** (this PR): `origination.py` + policy + proposal schema +
  fenced-record writer + full adversarial suite (directive §10) +
  generic acceptance run against the Gamma estate's real evidence (no
  TASK-017-specific code). Read-only with respect to the DAG/governor —
  produces a roadmap projection file only.
- **Phase 2A-2** (separate PR, after 2A-1 is independently verified):
  governor-side adapter that turns a project's `next_unlock` into a real
  `WorkNode`, O1 execution-boundary enforcement, lease/dispatch
  integration, and the full multi-process demo (directive §9).
