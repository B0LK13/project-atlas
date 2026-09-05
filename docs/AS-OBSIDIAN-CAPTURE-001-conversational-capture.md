# AS-OBSIDIAN-CAPTURE-001 — Conversational Knowledge Capture & Obsidian Bridge

Local-first capture of transient text (clipboard, stdin, CLI, and later a
localhost API / browser extension) into **durable, deduplicated, traceable raw
evidence**, plus a derived Obsidian Markdown projection.

Package ID: `AS-OBSIDIAN-CAPTURE-001`.
Source architecture: `docs/architecture/AS-OBSIDIAN-CAPTURE-001-architecture-source.md`.

Ordering is the architecture's north star, and it is enforced in code:

```text
PRESERVE FIRST -> UNDERSTAND SECOND -> PRESENT THIRD
```

## Package identity — why not `AS-OBS-001`

The source architecture document is titled **AS-OBS-001**. That identifier is
**already taken** in this repository by the *Operational Health Snapshot*
package (`src/project_atlas/ops_health.py`, `ops-health-snapshot.schema.json`,
`tests/unit/test_as_obs_001_health_snapshot.py`), which is marked **CLOSED** and
is consumed by `AS-OBS-002` (operational events) and `AS-OBS-003` (ops-report).
In this repository `OBS` means *observability*, not *Obsidian*.

Reusing `AS-OBS-001` would have collided with a closed package's contract,
schema registry entry, and CLI wiring. This work therefore ships as
`AS-OBSIDIAN-CAPTURE-001`. Nothing else about the architecture changed.

## What is delivered

| Concern | Module |
| --- | --- |
| Source adapters (text / stdin / clipboard), `CaptureRequest` | `capture_sources.py` |
| Capture service, raw repository, dedupe, routing, lifecycle | `obsidian_capture.py` |
| Obsidian Markdown output adapter | `obsidian_capture_note.py` |
| Raw capture contract | `schemas/raw-capture.schema.json` |
| Configuration (`[tool.atlas.capture]`, `[tool.atlas.obsidian]`) | `config.py` |

## Commands

```bash
atlas capture text --vault <vault> --text "Important information"
atlas capture text --vault <vault> --stdin
atlas capture text --vault <vault> --clipboard \
    --source-type conversation --application chatgpt --project harbor-api
atlas capture raw-list --vault <vault> [--project <id>] [--json]
atlas capture retry    --vault <vault> --capture-id rcap-...
atlas capture show     --vault <vault> --capture-id rcap-...   # verbatim evidence
```

Exit codes: `0` when the capture and its projection both succeed (or the
capture was a duplicate), `1` when the raw capture failed **or** when the
projection failed after evidence was preserved (`status: "partial"`). A partial
result never looks like success, and the raw evidence is always recoverable
with `atlas capture show` and resumable with `atlas capture retry`.

## Storage layout

```text
<vault>/generated/ops/raw-captures/
    rcap-<16hex>.json      # schema-validated capture record
    rcap-<16hex>.txt       # VERBATIM raw evidence (INV-001)
    latest.json

<vault>/generated/obsidian/captures/          # default projection root
    00 Inbox/Atlas Captures/
    10 Projects/<project-id>/{Conversations,Decisions,Research,Directives,Notes}/
    20 Decisions/  30 Research/  40 Directives/
```

An external Obsidian vault is **opt-in** (`--obsidian-vault`, or
`[tool.atlas.obsidian] vault_path`). By default Atlas writes nothing outside
`--vault`.

## Identity model

Three distinct concepts, deliberately never conflated (architecture §7):

- **`content_hash`** — `sha256` over the *canonical* content. Canonicalization
  is conservative: Unicode NFC plus line-ending normalization to `\n`, and
  **nothing else**. Indentation and leading/trailing whitespace are
  semantically relevant and are preserved.
- **`identity_hash`** — the logical capture: `content_hash` scoped by
  `project_id`, `source_type` and `source_application`. The same text captured
  into two projects is two captures; the same text pasted via `--text` and
  piped via `--stdin` is one (the transport is provenance, not identity).
- **`capture_id`** — `rcap-<first 16 hex of sha256(identity_hash)>`.

Deriving the id from content makes the filesystem the dedupe index: the lookup
is an `is_file()` on a deterministic path. Two concurrent identical captures
resolve to the same path with identical bytes, so the duplicate race of
architecture §49 cannot occur — no lock and no mutable index are needed.

## Decisions where repository truth overrode the architecture document

The source architecture repeatedly states that repository truth takes
precedence. Four places where it did:

### 1. No generated wall-clock values (NFR-001 / ADR-001 §2)

The architecture illustrates `created:`/`updated:` frontmatter and a
`YYYY-MM-DD-slug.md` filename. Atlas forbids wall-clock timestamps in generated
content, so:

- filenames are `<slug>-<capture_id>.md` — readable, and collision-safe by id
  rather than by date;
- no `created`/`updated` frontmatter is emitted;
- `captured_at` (architecture §39) is **operator-supplied only**
  (`--captured-at`). When omitted it is `null` with
  `captured_at_source: "not-provided"` — Atlas records UNKNOWN rather than
  inventing "now".

Rendering the same capture twice is byte-identical, which is what makes
idempotent retry and dedupe testable.

### 2. Raw evidence vs. the frozen conversational plane (D-042 / CAPTURE-002)

`conversation_capture.py` deliberately refuses raw transcripts
(`RAW_TRANSCRIPT_FORBIDDEN`) and is on the demo-isolation **DENY** list. That
prohibition is **not** relaxed. This package owns a *separate*, explicitly
quarantined evidence plane:

- raw captures are never written into `generated/ops/inbox/` and are never
  promoted to the Truth Core;
- turning captured evidence into structured knowledge remains an explicit human
  step through `atlas capture conversation`.

So `PRESERVE FIRST` is satisfied without weakening an existing governance
boundary, and INV-001 and D-042 both hold.

### 3. Secrets: preserve raw, redact derived (§38 + NFR-004)

Architecture §38 says the MVP should not redact raw capture, because rewriting
content would violate raw-evidence preservation. NFR-004/CODEX-SEC-006 says
secret material must not be persisted as metadata. Both are honoured:

| Artifact | Behaviour |
| --- | --- |
| `rcap-*.txt` raw evidence | **verbatim**, never rewritten |
| capture record `secret_scan.findings` | pattern *names* only, never the value |
| capture record `title` | redacted — the title becomes the **filename on disk** |
| Obsidian note | redacted via `redact_text` |

The title case matters: the derived title feeds the note's filename, so an
unredacted secret on the first captured line would reach the filesystem even
with a redacted note body.

### 4. Deterministic-only processing

There is no summarizer and no AI enrichment. The projection prints `UNKNOWN`
for Summary/Decisions/Actions rather than inventing them, and
`[tool.atlas.capture.processing] ai_enrichment` defaults to `false`. INV-004
(basic capture works offline, with no model provider) is covered by test.

## Invariants covered by tests

| Invariant | Test |
| --- | --- |
| INV-001 raw evidence preservation | `test_raw_evidence_survives_rendering_failure`, `test_raw_content_is_stored_verbatim_not_canonicalized` |
| INV-002 projection is not source | `test_note_is_marked_managed_and_non_canonical` |
| INV-003 stable identity | `test_content_hash_and_identity_hash_are_not_conflated` |
| INV-004 no external dependency | `test_capture_works_with_no_model_provider_available` |
| INV-005 local-first | `test_capture_declares_no_external_transmission`, `test_capture_writes_nothing_outside_the_vault_by_default` |
| INV-006 idempotent processing | `test_reprocessing_is_idempotent_and_deterministic`, `test_duplicate_capture_creates_no_second_record_or_note` |
| INV-007 failure isolation | `test_raw_evidence_survives_rendering_failure`, `test_failed_render_is_resumable_via_retry` |
| §62 path traversal | `test_routing_traversal_values_are_rejected`, `test_note_write_rejects_symlink_escape` |
| §62 unicode | `test_unicode_dutch_emoji_and_code_blocks_are_preserved` |
| §62 provenance | `test_note_capture_id_resolves_to_the_persisted_capture` |
| §35 YAML serialization | `test_frontmatter_survives_yaml_hostile_titles` |
| §49 concurrency | `test_concurrent_identical_captures_produce_one_capture` |
| §64 markdown injection | `test_captured_content_cannot_forge_atlas_region_markers` |

## Deliberately not delivered (and why)

- **Localhost capture API (§23) / browser extension (§25).** `LIVE_API`
  (`atlas live api-serve`) is a contractually **read-only** surface; adding a
  write endpoint would break a documented boundary and belongs in its own
  work package with its own review. The extension seam is nonetheless ready:
  every entry point converges on `obsidian_capture.capture()`, `source_adapter`
  already accepts `"api"`, and `CaptureResult` is the shared machine contract —
  so adding the API is an adapter, not an architecture rewrite (§66).
- **AI enrichment (§10.2), conversation-level message parsing (§41),
  knowledge-graph relations (§42).** Explicit AS-OBS-002-class follow-ups. The
  record model already carries `derived_artifacts[]` so one capture can yield N
  artifacts (§58) without a schema migration.
- **Automatic Atlas source registration / ingest.** Deriving structured claims
  from raw text is exactly the `transcript_extraction` that D-042 defers. The
  capture record carries everything a later bridge needs.
