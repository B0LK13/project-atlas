# PROJECT ATLAS — UNIVERSAL AUTONOMOUS AGENT BOOTSTRAP, STABILIZATION, AND CONTINUATION DIRECTIVE

AGENT:
<AGENT NAME>

PROJECT:
Project Atlas

DIRECTIVE ID:
D-PROJECT-ATLAS-UNIVERSAL-AGENT-BOOTSTRAP-001

MODE:
AUTONOMOUS REPOSITORY ORIENTATION, STABILIZATION, EXECUTION, REVIEW, AND CONTINUATION

PROJECT OWNER INTERACTION:
EXCEPTION-ONLY

FINAL MERGE:
PROJECT OWNER AUTHORIZATION REQUIRED

PRODUCTION DEPLOYMENT:
PROJECT OWNER AUTHORIZATION REQUIRED

DESTRUCTIVE OPERATIONS:
PROHIBITED UNLESS EXPLICITLY AUTHORIZED

HISTORY REWRITE:
PROHIBITED

FORCE PUSH:
PROHIBITED

DEFAULT WORKING PRINCIPLE:
TRUST REPRODUCIBLE REPOSITORY EVIDENCE, NOT PRIOR AGENT NARRATIVE

---

# 1. Mission

You are taking over Project Atlas from previous agents whose sessions may have ended, lost context, exhausted credits, or left partially completed work.

Your job is to:

1. reconstruct the exact current repository state;
2. identify active, completed, superseded, blocked, and abandoned work;
3. stabilize the working environment;
4. determine the true critical path;
5. continue the highest-priority valid work package;
6. preserve all historical evidence;
7. avoid repeating already completed work;
8. repair inaccurate or stale project-state records additively;
9. run complete quality gates;
10. perform an isolated technical review where warranted;
11. prepare merge-ready work;
12. continue into the next approved roadmap phase after merge;
13. escalate only genuine owner decisions.

Do not assume that any prior report, chat summary, roadmap, worklog entry, candidate label, evidence receipt, branch description, or agent statement is correct until verified.

Do not ask the owner to restate information that can be discovered from the repository.

---

# 2. Universal evidence rule

Adopt immediately:

NO REPOSITORY-STATE CLAIM WITHOUT REPRODUCIBLE EVIDENCE

Every material state claim must include:

CLAIM:
one falsifiable sentence

COMMAND:
exact non-interactive command used

TARGET:
commit, branch, tag, path, worktree, or remote inspected

OUTPUT:
verbatim or accurately bounded output

TIMESTAMP:
ISO-8601 with timezone offset

ENVIRONMENT:
OS, shell, Python version, repository path, worktree state

LIMITATIONS:
what the evidence does not prove

Examples of claims requiring evidence:

- worktree is clean;
- branch is pushed;
- tag exists remotely;
- tests passed;
- integration suite is meaningful;
- file is ignored;
- candidate is frozen;
- no active writer exists;
- source identity is stable;
- CI is green;
- work package is complete;
- evidence is accurate;
- current roadmap is authoritative.

Do not create a new governance platform for this rule.

Use it as a response and evidence convention.

---

# 3. Repository discovery

Locate the repository without relying solely on the provided path.

Likely locations may include:

D:\project-atlas-vault
D:\project-atlas
D:\development\project-atlas
other registered Git worktrees

Run read-only discovery first.

Capture:

- repository root;
- Git common directory;
- active worktree path;
- all registered worktrees;
- current branch;
- current HEAD;
- current tree;
- origin URL;
- local remote-tracking refs;
- untracked files;
- staged files;
- unstaged files;
- merge/rebase/cherry-pick/bisect state;
- index locks;
- active Git processes;
- local-only configuration affecting checkout, signing, hooks, or line endings.

Recommended commands:

git rev-parse --show-toplevel
git rev-parse --git-common-dir
git worktree list --porcelain
git branch --show-current
git rev-parse HEAD
git rev-parse HEAD^{tree}
git status --porcelain=v1
git status --branch --short
git remote -v
git log --oneline --decorate --graph -30
git tag --list --sort=creatordate
git config --show-origin --list

Do not mutate the repository during discovery.

---

# 4. Lock and writer safety

Before any mutation, inspect:

- `.git/index.lock`;
- worktree-specific lock files;
- active Git processes;
- IDE source-control operations;
- Python processes writing project files;
- test runners;
- file watchers;
- other coding agents;
- terminals with the repository as working directory.

Classify any lock as:

TRANSIENT BENIGN LOCK
ACTIVE WRITER LOCK
STALE ORPHANED LOCK
UNKNOWN

Do not delete a lock solely because it is zero bytes.

Determine:

- owner process;
- PID;
- command;
- start time;
- working directory;
- open handle where possible;
- timestamp and timezone consistency.

If ownership cannot be proven, preserve the lock and use an isolated worktree.

---

# 5. Preserve history and artifacts

Do not:

- reset;
- amend;
- rebase;
- squash;
- force-push;
- delete tags;
- move tags;
- overwrite evidence;
- delete historical receipts;
- delete ADRs;
- rewrite WORKLOG history;
- remove prior candidate records;
- delete old branches solely because they look stale.

Existing tags, commits, evidence receipts, worklogs, ADRs, and candidate records are historical facts even when superseded.

Correct inaccurate state through:

- additive commits;
- supersession records;
- evidence amendments;
- new candidate versions;
- explicit status corrections.

Never silently edit historical evidence to make it appear originally correct.

---

# 6. Reconstruct the project timeline

Inspect at minimum:

- `WORKLOG.md`;
- `docs/backlog.md`;
- roadmap documents;
- `docs/adr/**`;
- `docs/evidence/**`;
- `docs/work-packages/**`;
- active branch commits;
- candidate tags;
- CI workflow;
- `pyproject.toml`;
- `CLAUDE.md`;
- `AGENTS.md`;
- README files;
- architecture amendments;
- migration plans;
- source-control or session-preservation artifacts.

Build an internal timeline containing:

WORK PACKAGE
BASE
IMPLEMENTATION COMMIT
EVIDENCE COMMIT
CANDIDATE TAG
REVIEW STATUS
CERTIFICATION STATUS
MERGE STATUS
SUPERSESSION
BLOCKERS

When documents disagree, prefer evidence in this order:

1. actual Git object and file content;
2. actual executable test result;
3. remote repository state;
4. signed or hashed evidence with matching objects;
5. accepted ADR or work-package contract;
6. WORKLOG;
7. roadmap;
8. backlog;
9. prior agent prose.

Do not infer completion from a plan document.

---

# 7. Known historical context to verify, not trust blindly

Previous agents reported that work centered on:

AS-CORE-003
Claim Identity v2, migration aliases, and ingestion OCC rollback

Previously reported objects included:

BASE:
4e2b4369e88978d5e743b47ae58c3129beed0f0f

EARLIER CODE CANDIDATE:
42f3912a7bfb25324d3b1d3f5c096213b7e375e2

EARLIER GOVERNANCE TIP:
6eb3c36bb78696dec8d180c2d1254ac803d667c1

LATER REPORTED TIP:
d356b7a

REPORTED CANDIDATES:
candidate/CAND-AS-CORE-003-V2-001
candidate/CAND-AS-CORE-003-V2-002

These references are context only.

Verify every object locally and remotely before using it.

Do not assume `d356b7a` is still HEAD.

Do not assume candidate V2-002 is valid or final.

---

# 8. Determine the active work package

Identify the current active work by examining:

- branch name;
- latest commits;
- uncommitted changes;
- candidate tags;
- evidence receipts;
- work-package documents;
- unresolved test failures;
- open PRs;
- CI;
- review findings.

Classify each discovered workstream as:

ACTIVE
IMPLEMENTED
REVIEW PENDING
CERTIFICATION PENDING
MERGE READY
MERGED
SUPERSEDED
ABANDONED
BLOCKED
UNKNOWN

Select only one primary active work package.

Secondary work may be recorded but must not contaminate the primary scope.

If the current branch mixes multiple packages, determine whether to:

A. review and certify the combined scope; or
B. preserve it and establish clean additive branches for separated future scope.

Do not rewrite history to simplify the narrative.

---

# 9. Stabilization before feature work

Before implementing new features, establish:

- clean or intentionally isolated worktree;
- correct Python version;
- working virtual environment;
- dependency installation;
- reproducible CLI;
- Git remote access;
- CI visibility;
- line-ending behavior;
- no active writer;
- no unresolved merge state;
- baseline quality-gate results.

Capture:

python --version
python -m pip --version
python -m pytest --collect-only -q
python -m ruff --version
python -m mypy --version
git ls-files --eol
git status --porcelain=v1

If the main implementation worktree is contaminated, do not normalize or reset it immediately.

Create an isolated verification worktree from the exact target commit.

---

# 10. Required quality-gate baseline

Run the project’s current declared gates before changing code.

At minimum:

python -m ruff check .
python -m mypy src
python -m pytest -p no:cacheprovider --tb=no
python -m pytest -p no:cacheprovider -m integration --tb=no
python -m compileall -q src tests

Run coverage if configured:

python -m pytest \
  --cov=src/project_atlas \
  --cov-report=term-missing \
  --cov-report=xml

Run exact CLI smoke commands from CI.

Record:

- command;
- exit code;
- passed;
- failed;
- skipped;
- deselected;
- errors;
- collection count;
- Python version;
- OS;
- commit;
- worktree state.

Do not describe `-m integration` as meaningful until marker coverage and test classification are inspected.

---

# 11. Verify integration-test semantics

Inspect every test module currently classified as integration.

For each module record:

MODULE
TEST COUNT
REAL FILESYSTEM
REAL CLI
REAL PIPELINE
MOCK HEAVINESS
CLASSIFICATION
MARKER APPROPRIATE

Do not assume that location under `tests/integration/` proves integration semantics.

Final evidence must distinguish:

UNIT
FUNCTIONAL
INTEGRATION
END-TO-END
REGRESSION
GOLDEN FIXTURE

---

# 12. Active AS-CORE-003 correctness checks

If AS-CORE-003 is still active or unmerged, verify all of the following before declaring it complete.

## Identity tuple encoding

Confirm that claim identity uses an injective deterministic encoding.

A raw delimiter-concatenated tuple is not acceptable unless every component is formally delimiter-safe.

Preferred:

- canonical compact JSON array; or
- length-prefixed encoding.

Identity input must include:

- identity version;
- project identity;
- source lineage identity;
- claim type;
- normalized field;
- stable semantic locator.

It must exclude:

- current claim value;
- value hash;
- mutable source position.

Compiler and migration must share one stable derivation contract.

## Alias ambiguity

An ambiguous mapping must not be consumable as a resolved alias.

Required invariant:

RESOLVED:
resolved collection only

AMBIGUOUS:
ambiguity collection only

PROMOTION:
prohibited until resolved

## Rule parity

Compiler and migration parsing or claim-rule behavior must be mechanically synchronized.

## OCC

Compare-and-swap failure must prove:

- no partial promotion;
- no unintended canonical mutation;
- injected external state preserved;
- temporary output not promoted;
- lock released;
- retry deterministic.

## Source-lineage normalization

Determine whether LF versus CRLF should change text-source identity.

Do not accept platform checkout behavior as an accidental semantic contract.

Document:

- text normalization;
- binary handling;
- hashing boundary;
- migration implications.

## ADR

A cross-cutting identity ADR must document the final contract.

Do not defer identity-boundary correctness to later parser work.

---

# 13. Candidate lifecycle

A candidate tag is immutable.

If any material code, schema, migration, test, fixture, ADR, CI, or authoritative evidence changes after a candidate freezes:

1. preserve the old candidate;
2. record why it was superseded;
3. create the next candidate sequence;
4. use a new tag;
5. bind the tag to one exact commit and tree;
6. distinguish:
   - code candidate;
   - evidence tip;
   - final PR head;
7. rerun all gates;
8. review the full final PR delta.

Never reuse an old candidate ID.

Never move a tag.

---

# 14. Isolated technical review

For high-risk changes, use an isolated technical review.

Requirements:

- fresh session;
- fresh clean clone or detached worktree;
- no implementation scratch state;
- read-only review authority;
- exact commit/tag binding;
- independent gate reproduction;
- no fixes made inside the review session.

Call this:

ISOLATED TECHNICAL REVIEW

Do not claim organizational independence when one owner controls all agents.

Allowed dispositions:

PASS
PASS WITH NON-BLOCKING FINDINGS
FAIL — REMEDIATION REQUIRED
BLOCKED — ENVIRONMENT NOT VERIFIABLE

If review fails, remediate additively and create a new candidate.

---

# 15. Scope discipline

Do not mix unrelated work into an active correctness package.

Examples of separate concerns:

- identity remediation;
- parser registry;
- `.gitattributes`;
- CI matrix;
- coverage;
- backlog reconciliation;
- README;
- retrieval CLI;
- governance experiments.

A combined package is allowed only when:

- the combined scope is explicitly classified;
- every changed path is reviewed;
- CI covers the full delta;
- evidence describes the real scope;
- final certification covers the full PR head.

Otherwise preserve the mixed branch and establish clean future work from the appropriate base.

---

# 16. Product-first project direction

After AS-CORE-003 is merged and closed, the project direction is product-first.

Do not automatically begin AS-ENG-006 through AS-ENG-010.

Those broad governance packages are frozen pending product validation.

The product thesis to test is:

Project Atlas is a deterministic, provenance-backed, offline repository knowledge compiler that tells a user:

- what the project currently claims;
- where each claim came from;
- what changed;
- what is stale;
- what conflicts;
- what is unsupported;
- what depends on what;
- what needs attention.

Governance is supporting infrastructure, not the primary product.

---

# 17. Post-merge product sequence

After AS-CORE-003 merge, use a new branch and clean worktree.

Execute in this order.

## Phase P0 — production self-host baseline

Run the current production CLI unchanged against Project Atlas itself.

Use an output path outside the repository.

Do not add anchors or optimize sources first.

Record:

- exact source commit;
- corpus manifest;
- files;
- lines;
- bytes;
- discover result;
- ingest result;
- parse failures;
- identity failures;
- runtime;
- memory;
- partial output;
- deterministic replay;
- exact failure stage.

A failure is valid evidence.

Do not fix during the baseline run.

## Phase P1 — parser framework and structured sources

Create a bounded product work package after revalidating IDs.

Suggested title:

Deterministic Documentation Parser Framework and Structured Source Extraction

First iteration should include:

- common parser output contract;
- parser registry;
- parser versioning;
- source-span ownership;
- diagnostics;
- existing key-value compatibility;
- structured YAML document parser;
- evidence receipt parser;
- ADR parser;
- frozen real-world fixtures.

Do not implement every parser at once.

## Phase P2 — Markdown work tracking

Only after P1 evidence supports it:

- task-list parser;
- labeled-list parser;
- table parser;
- work-item identity;
- multidimensional lifecycle state;
- historical backlog fixture.

## Phase P3 — generic fallback and corpus hardening

Then:

- front matter;
- heading-scoped fallback;
- provisional locators;
- mixed-document handling;
- full RAW corpus hardening;
- performance metrics;
- withheld-claim reporting.

---

# 18. Parser architecture principles

Structure must be preserved before identity is derived.

Preferred flow:

SOURCE CLASSIFICATION
→ SPECIFIC PARSER SELECTION
→ SOURCE REGION OWNERSHIP
→ PARSED CLAIM CANDIDATES
→ STABLE SEMANTIC LOCATOR
→ CLAIM IDENTITY
→ LIFECYCLE
→ CONFLICT PROCESSING
→ VALIDATION
→ ATOMIC PROMOTION

Specific structured parsers outrank generic line regexes.

Examples:

- evidence YAML;
- ADR structure;
- YAML-bodied document;
- Markdown table;
- task list;
- labeled list;
- key-value fallback.

Do not run generic regex extraction over structured YAML that has already been parsed.

---

# 19. Parser output contract

Parser output should include at minimum:

parser_id
parser_version
claim_type
subject
normalized_field
raw_value
normalized_value
stable_semantic_locator
locator_kind
locator_confidence
source_path
source_span
heading_path
structural_context
authority_hint
ambiguity_status

Parser output must not compute the final claim ID.

Claim identity is a separate shared contract.

Every emitted claim must retain parser provenance.

---

# 20. Locator hierarchy

Preferred locator priority:

1. explicit validated stable ID;
2. schema-defined record key;
3. table row key;
4. task or work-item ID;
5. YAML path;
6. full heading path plus normalized label;
7. deterministic structural key;
8. unresolved/manual review.

Never use as durable identity:

- line number;
- byte offset;
- claim value;
- value hash;
- absolute machine path.

Structural ordinals are provisional only.

They must be visibly marked low-confidence and must not silently drive conflict or supersession decisions.

---

# 21. Repeated-claim semantics

Duplicate locator does not automatically mean conflict.

Determine in order:

1. parser duplicate;
2. separate structured subjects;
3. repeated historical observations;
4. explicit supersession;
5. same subject and field with competing current values;
6. unresolved ambiguity;
7. parser failure.

Only competing currently authoritative claims should become semantic conflicts.

Do not infer currentness solely from line order.

Do not flatten multidimensional lifecycle state into one binary completion field.

---

# 22. Compilation outcome model

Parser work must define:

COMPLETE
PARTIAL
FAILED

At minimum record:

recognized_candidates
promoted_claims
withheld_claims
diagnostics
review_queue_entries

A partial run may not be presented as complete.

An unresolved identity may not be silently promoted.

A per-claim failure may continue processing only when the final result explicitly reports partial status.

---

# 23. Self-hosting acceptance levels

Use:

LEVEL 0:
pipeline survives

LEVEL 1:
traceable output

LEVEL 2:
useful output

LEVEL 3:
trustworthy output

LEVEL 4:
operational product

Do not declare success at Level 0.

The key product measurement is:

RAW CORPUS RESULT
versus
ATLAS-OPTIMIZED CORPUS RESULT

This reveals whether Atlas reads existing documentation or requires users to rewrite documentation for Atlas.

---

# 24. Product differentiators

After self-host evidence, prioritize capabilities that move real user questions from unsupported to supported.

Default priority:

1. change report between compilations;
2. severity-aware validation exit codes;
3. freshness validation;
4. retrieval CLI;
5. claim explanation;
6. authority-aware current-state view;
7. orphan detection;
8. impact graph later.

A feature must answer a real product question.

If it does not, defer it.

---

# 25. Engineering signals

Maintain or establish:

- meaningful integration classification;
- coverage baseline;
- module-level coverage;
- deterministic CI environment;
- Windows CI;
- supported Python compatibility matrix;
- line-ending policy;
- dependency lock or constraints;
- README;
- complete CLI reference.

Do not treat a high global coverage percentage as proof that critical paths are tested.

Inspect coverage specifically for:

- ingestion;
- knowledge compiler;
- migrations;
- identity;
- lifecycle;
- conflict handling;
- retrieval.

---

# 26. Maintainability refactoring

Only after coverage and parser behavior stabilize:

- decompose `_ingest`;
- decompose `_apply_lifecycle`;
- reduce private-function imports in tests;
- centralize stable claim rules;
- create stage interfaces;
- add performance benchmarks.

Do not mix this refactor with parser-registry work.

---

# 27. Workflow simplification

Keep:

- candidate tags;
- compact evidence receipts;
- additive history;
- isolated technical review;
- exact command evidence;
- historical WORKLOG.

Simplify:

- directives;
- checkpoints;
- review role language;
- evidence forms;
- clean-clone procedures by folding repeatable checks into CI.

Freeze:

- AS-ENG-006 through AS-ENG-010 governance expansion;
- sibling control-plane expansion;
- speculative lease infrastructure.

Disable prospectively:

- automatic tag signing unless deliberately approved;
- routine CP checkpoint files;
- simulated organizational independence.

Never remove:

- Git history;
- existing tags;
- ADRs;
- evidence receipts;
- WORKLOG history.

---

# 28. Autonomous continuation rules

Do not stop after producing a plan.

Proceed through:

1. discovery;
2. stabilization;
3. baseline gates;
4. active-package reconstruction;
5. remediation;
6. new candidate;
7. isolated technical review;
8. final certification;
9. CI and PR verification;
10. merge-ready return.

After owner-authorized merge:

11. create fresh branch/worktree;
12. capture self-host baseline;
13. open bounded parser-framework package;
14. execute test-driven implementation;
15. rerun self-host experiment;
16. update product roadmap from evidence.

Routine failures remain your responsibility.

---

# 29. Hard escalation conditions

Ask the Project Owner only when:

1. destructive history or migration is required;
2. repository credentials or permissions block required work;
3. branch separation cannot be achieved safely without prohibited history rewrite;
4. a material architecture choice has multiple equally defensible options with major compatibility consequences;
5. a security risk requires explicit acceptance;
6. production deployment is requested;
7. final merge authorization is ready;
8. two bounded parser iterations falsify the product thesis;
9. repository corruption or data loss risk is credible;
10. owner-only secrets or external systems are required.

Do not escalate:

- ordinary test failures;
- lint failures;
- CI failures;
- candidate resequencing;
- documentation corrections;
- marker fixes;
- isolated worktree creation;
- regression test additions;
- parser iteration;
- non-destructive branch creation.

---

# 30. Required agent updates

During long-running work, report only meaningful milestones.

Examples:

- repository state reconstructed;
- active package identified;
- blocker found;
- quality baseline established;
- finding validated;
- candidate frozen;
- isolated review completed;
- merge-ready.

Do not send repetitive low-level command narration.

Do not ask for confirmation after each commit.

---

# 31. Required final response before merge

Return only:

AGENT:
<agent>

PROJECT:
Project Atlas

DIRECTIVE ID:
D-PROJECT-ATLAS-UNIVERSAL-AGENT-BOOTSTRAP-001

STATUS:
MERGE READY / BLOCKED

REPOSITORY:
<exact>

BRANCH:
<exact>

BASE:
<full hash>

FINAL PR HEAD:
<full hash>

FINAL TREE:
<full hash>

FINAL CANDIDATE:
<exact>

FINAL TAG:
<exact>

SCOPE:
<exact>

QUALITY GATES:
<commands and results>

INTEGRATION GATE:
<exact>

COVERAGE:
<exact>

ISOLATED TECHNICAL REVIEW:
<disposition>

FINAL CERTIFICATION:
<disposition>

CI:
<exact>

PR:
<exact>

UNRESOLVED FINDINGS:
NONE / <complete>

BLOCKERS:
NONE / <complete>

NEXT PROJECT OWNER ACTION:
AUTHORIZE MERGE / <exact decision>
