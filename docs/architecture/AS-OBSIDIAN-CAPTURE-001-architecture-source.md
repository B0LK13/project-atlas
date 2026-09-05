> [!IMPORTANT]
> **Package identifier superseded.** This document was delivered titled
> `AS-OBS-001`. That identifier is **already owned** by the CLOSED
> *Operational Health Snapshot* package (`src/project_atlas/ops_health.py`,
> `ops-health-snapshot.schema.json`,
> `tests/unit/test_as_obs_001_health_snapshot.py`), consumed by `AS-OBS-002`
> (operational events) and `AS-OBS-003` (ops-report). In this repository
> `OBS` denotes **observability**, not Obsidian.
>
> Every occurrence of `AS-OBS-001` **below** refers to this Obsidian capture
> work and is superseded by the canonical repository identity:
>
> ```text
> AS-OBSIDIAN-CAPTURE-001
> ```
>
> The existing observability package is unchanged and must not be renamed.
> This file is retained verbatim as the delivered architecture of record; see
> `docs/AS-OBSIDIAN-CAPTURE-001-conversational-capture.md` for what was built,
> and for the four places where repository truth overrode this document.

---

# AS-OBS-001 Architecture

## Conversational Knowledge Capture & Obsidian Bridge

**Status:** Proposed Architecture
**Work Package:** AS-OBS-001
**System:** Project Atlas
**Primary Platform:** Ubuntu 26
**Primary Human Interface:** Obsidian
**Initial Capture Sources:** Clipboard, stdin, conversational AI output
**Architecture Principle:** Capture → Preserve → Understand → Connect

---

# 1. Purpose

AS-OBS-001 introduces a first-class knowledge capture subsystem into Project Atlas.

Its purpose is to transform transient information — initially text copied from ChatGPT or other LLM conversations — into durable, traceable, deduplicated and queryable Atlas knowledge while simultaneously rendering that knowledge into a human-friendly Obsidian vault.

The feature must not reduce Atlas to an Obsidian automation utility.

The architectural ownership model is:

```text id="xq2myq"
Atlas
├── owns source identity
├── owns capture identity
├── owns provenance
├── owns immutable raw evidence
├── owns deduplication
├── owns lifecycle state
├── owns ingestion
├── owns knowledge/query integration
└── orchestrates output adapters

Obsidian
├── presents human-readable notes
├── provides manual editing/navigation
├── provides wikilink-based exploration
└── acts as a human knowledge workspace
```

The Obsidian note is therefore a projection of Atlas-managed knowledge, not the sole canonical source.

---

# 2. Architectural Goals

The architecture SHALL provide:

1. local-first capture;
2. immutable preservation of original captured content;
3. deterministic content identity;
4. deduplication;
5. provenance and lineage;
6. extensible input adapters;
7. extensible output adapters;
8. deterministic operation without requiring an external LLM;
9. safe Obsidian Markdown generation;
10. project-aware routing;
11. Atlas ingestion integration;
12. recoverable processing failures;
13. idempotent reprocessing;
14. localhost API support;
15. future browser-extension compatibility.

The architecture SHOULD make it possible to later add:

* ChatGPT-specific browser capture;
* Claude capture;
* Codex capture;
* Kimi capture;
* GitHub capture;
* terminal capture;
* email capture;
* PDF capture;
* webpage capture;
* AI summarization;
* task extraction;
* decision extraction;
* contradiction detection;
* semantic note linking;
* automatic knowledge graph generation.

---

# 3. Non-Goals

AS-OBS-001 is not intended to deliver all conversational intelligence functionality in the first iteration.

The MVP does NOT require:

* a full browser DOM scraper;
* automatic ChatGPT login/session handling;
* remote cloud sync;
* autonomous deletion of low-value content;
* mandatory LLM summarization;
* semantic vector clustering of every capture;
* automatic mutation of arbitrary existing Obsidian notes;
* multi-user collaboration;
* remote network capture endpoints;
* replacing Obsidian's own sync mechanisms;
* a permanently running daemon unless repository architecture already requires one.

These belong to later work packages where justified.

---

# 4. Architectural Invariants

The following invariants are mandatory.

## INV-001 — Raw evidence preservation

A successfully accepted capture must have a recoverable representation of the original content.

Generated notes may change.

The original capture must not be silently rewritten.

---

## INV-002 — Projection is not source

An Obsidian Markdown note is not the authoritative evidence object unless existing Atlas architecture explicitly defines source objects that way.

Atlas must retain lineage between:

```text id="hv6dc8"
raw capture
    ↓
processed representation
    ↓
Obsidian note
    ↓
Atlas knowledge index
```

---

## INV-003 — Stable identity

Every accepted logical capture must have stable identity.

Where Atlas already provides source IDs, durable lineage IDs, content hashes or project IDs, those MUST be reused.

Do not create parallel competing identity schemes.

---

## INV-004 — No external dependency for basic capture

Basic capture SHALL work without an external model provider.

For example:

```text id="bqlqbt"
clipboard
→ Atlas capture
→ raw persistence
→ deterministic Markdown rendering
→ Obsidian
```

must remain possible offline.

---

## INV-005 — Local-first

No captured content leaves the local machine unless the user explicitly configures functionality that requires a remote provider.

---

## INV-006 — Idempotent processing

Reprocessing an already persisted capture SHALL NOT produce uncontrolled duplicate outputs.

---

## INV-007 — Failure isolation

Failure in optional enrichment, Obsidian rendering or Atlas indexing SHALL NOT destroy successfully persisted raw evidence.

---

# 5. High-Level Architecture

```text id="js6i2x"
┌─────────────────────────────────────────────────────────────┐
│                       INPUT SOURCES                         │
│                                                             │
│  Clipboard   stdin   CLI text   Browser Extension   Future │
└───────┬────────┬─────────┬─────────────┬────────────────────┘
        │        │         │             │
        └────────┴─────────┴─────────────┘
                         │
                         ▼
              ┌────────────────────┐
              │   Source Adapter   │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │   CaptureService   │
              │                    │
              │ validation         │
              │ canonicalization   │
              │ identity           │
              │ deduplication      │
              │ persistence        │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │ Canonical Capture  │
              │     Repository     │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │ Processing Pipeline│
              │                    │
              │ deterministic      │
              │ optional AI        │
              │ routing            │
              │ linking            │
              └─────────┬──────────┘
                        │
             ┌──────────┴───────────┐
             │                      │
             ▼                      ▼
┌────────────────────────┐  ┌──────────────────────┐
│ Obsidian Output Adapter│  │ Atlas Source/Ingest  │
└────────────┬───────────┘  └──────────┬───────────┘
             │                         │
             ▼                         ▼
┌────────────────────────┐  ┌──────────────────────┐
│    Obsidian Vault      │  │ Index / Query Layer  │
└────────────────────────┘  └──────────────────────┘
```

---

# 6. Component Model

The exact repository modules SHALL be determined from repository truth.

The conceptual components below define responsibilities rather than mandatory filenames or class names.

---

# 6.1 SourceAdapter

The SourceAdapter converts source-specific input into a canonical CaptureRequest.

Conceptual contract:

```text id="h2bcwo"
SourceAdapter
    input:
        provider-specific data

    output:
        CaptureRequest
```

Examples:

```text id="75cxbo"
ClipboardSourceAdapter
StdinSourceAdapter
TextSourceAdapter
BrowserSourceAdapter
```

Future:

```text id="a10pg1"
ChatGPTSourceAdapter
ClaudeSourceAdapter
CodexSourceAdapter
GitHubSourceAdapter
EmailSourceAdapter
TerminalSourceAdapter
```

Adapters SHOULD contain source-specific acquisition logic only.

They SHOULD NOT own:

* raw persistence;
* deduplication;
* Obsidian generation;
* Atlas indexing;
* AI enrichment.

---

# 6.2 CaptureRequest

Conceptual schema:

```text id="0mojgr"
CaptureRequest
├── content
├── source_type
├── source_application
├── project_reference?
├── title_hint?
├── source_locator?
├── source_metadata?
├── capture_mode?
└── requested_outputs?
```

Minimum required field:

```text id="e7r69n"
content
```

Potential source types:

```text id="f0h4j2"
text
conversation
terminal
web
email
document
agent_output
```

Potential source applications:

```text id="f95pd8"
chatgpt
claude
codex
kimi
terminal
browser
clipboard
unknown
```

These enums SHOULD remain extensible.

---

# 6.3 CaptureService

The CaptureService is the central orchestration boundary for capture.

All capture entry points MUST converge here.

Example:

```text id="r0ax6z"
CLI
    ┐
API ├──> CaptureService
GUI ┤
Ext ┘
```

This avoids divergent behavior between CLI, API and future browser integrations.

Responsibilities:

1. validate CaptureRequest;
2. normalize/canonicalize content for identity purposes;
3. calculate or request content identity;
4. check deduplication state;
5. create capture identity;
6. persist canonical raw capture;
7. associate provenance/project lineage;
8. trigger downstream processing;
9. return structured CaptureResult.

The CaptureService SHOULD NOT directly contain Obsidian-specific path logic.

---

# 6.4 Canonical Capture Repository

This repository persists original capture evidence and lifecycle metadata.

Conceptually:

```text id="7llhva"
CaptureRecord
├── capture_id
├── source_id
├── project_id?
├── source_type
├── source_application
├── captured_at
├── content_hash
├── raw_content
├── metadata
├── lifecycle_state
├── provenance
└── derived_artifacts
```

Actual persistence SHOULD reuse existing Atlas storage primitives.

Possible storage representations, subject to repository truth:

```text id="3v6j3r"
JSON
SQLite
Atlas source registry
filesystem object
existing metadata store
```

Do not introduce a new database if Atlas already has a suitable durable source model.

---

# 7. Identity Model

Identity consists of multiple distinct concepts.

They MUST NOT be conflated.

---

## 7.1 Capture ID

Uniquely identifies the capture event/object.

Example conceptual value:

```text id="74dsiv"
cap_01K...
```

Existing Atlas ID conventions SHALL take precedence.

---

## 7.2 Source ID

Connects the capture to Atlas source lineage.

A source may represent the logical information origin.

Example:

```text id="6oaj36"
src_01K...
```

If Atlas already models durable source identity, AS-OBS-001 MUST reuse it.

---

## 7.3 Content Hash

Represents deterministic content identity.

Preferred algorithm:

```text id="ywly19"
SHA-256
```

unless Atlas already has another cryptographic content-addressing mechanism.

Conceptually:

```text id="z81uiq"
content_hash =
    SHA256(canonical_content_representation)
```

Canonicalization rules MUST be documented and tested.

Do not accidentally normalize semantically relevant content.

A conservative initial canonicalization policy is preferred.

For example:

```text id="h2dwmf"
UTF-8 encode
preserve content
normalize transport-only representation where safe
```

Avoid aggressive whitespace stripping unless repository requirements explicitly justify it.

---

# 8. Deduplication Architecture

Deduplication occurs before generating a new projected note.

Conceptual flow:

```text id="7fsarg"
CaptureRequest
     │
     ▼
canonicalize
     │
     ▼
content hash
     │
     ▼
lookup existing capture
     │
     ├── exists ──> DuplicateCaptureResult
     │
     └── new ─────> Persist
```

Deduplication must distinguish:

```text id="mwitrl"
same content
same logical source
same capture event
```

These are not necessarily identical concepts.

MVP MAY use content-hash deduplication.

Future versions may scope dedupe by:

```text id="1olw0j"
project
source application
conversation ID
source locator
capture window
```

The architecture SHALL permit this evolution.

---

# 9. Provenance Model

Every output should be traceable to its capture.

Conceptual lineage:

```text id="d917td"
External Information
        │
        ▼
CaptureRequest
        │
        ▼
CaptureRecord
        │
        ├── derived_from
        │
        ▼
ProcessedKnowledge
        │
        ├── rendered_as
        │
        ▼
ObsidianNote
        │
        └── ingested_as
                │
                ▼
           AtlasSource
```

Metadata SHOULD support equivalent relationships.

Example:

```text id="8e48mr"
capture_id
source_id
derived_from
generated_from
content_hash
captured_at
processed_at
written_at
```

Reuse existing Atlas provenance terminology where available.

---

# 10. Processing Pipeline

The processing pipeline converts raw evidence into useful knowledge representations.

It MUST support a deterministic mode.

Conceptual stages:

```text id="i5mnhh"
VALIDATE
    ↓
PERSIST
    ↓
DEDUPLICATE
    ↓
CLASSIFY
    ↓
ROUTE
    ↓
ENRICH
    ↓
RENDER
    ↓
INGEST
```

Only the first persistence boundary is mandatory for acceptance of capture.

---

# 10.1 Deterministic processing

MVP deterministic operations may include:

* source metadata extraction;
* timestamp generation;
* project assignment from explicit CLI/API value;
* title generation from safe heuristics;
* Markdown rendering;
* frontmatter serialization;
* basic known identifier linking;
* routing to Inbox when uncertain.

---

# 10.2 Optional AI enrichment

AI enrichment SHALL be an optional processor.

Conceptually:

```text id="dabf0r"
KnowledgeProcessor
├── DeterministicProcessor
└── AIEnrichmentProcessor
```

AI enrichment MAY later produce:

```text id="2dbgek"
summary
decisions
actions
entities
tags
project classification
note suggestions
relationships
```

It SHALL NOT be required to preserve raw content.

---

# 11. Processing Result

Conceptual representation:

```text id="jkg0hj"
ProcessedCapture
├── capture_id
├── title
├── summary?
├── content
├── classification
├── project
├── tags
├── entities
├── decisions
├── actions
├── links
└── processing_metadata
```

In AS-OBS-001 many optional fields may remain empty.

The contract should nonetheless allow AS-OBS-002 to populate them.

---

# 12. Output Adapter Architecture

Atlas SHALL support output adapters.

Conceptual interface:

```text id="2t6ucg"
OutputAdapter

render(processed_capture)
write(rendered_output)
```

Initial implementation:

```text id="nnywuc"
ObsidianMarkdownAdapter
```

Future examples:

```text id="br5756"
PlainMarkdownAdapter
JSONExportAdapter
HTMLAdapter
NotionAdapter
StaticSiteAdapter
```

The CaptureService MUST NOT depend on Obsidian-specific implementation details.

---

# 13. ObsidianMarkdownAdapter

Responsibilities:

1. determine logical note destination;
2. safely resolve configured vault path;
3. serialize YAML frontmatter;
4. render Markdown body;
5. sanitize filenames;
6. prevent path escape;
7. write atomically where practical;
8. detect conflicting outputs;
9. return note artifact metadata.

Conceptual output:

```text id="8cl0sj"
ObsidianArtifact
├── vault_path
├── relative_note_path
├── absolute_note_path
├── generated_at
├── capture_id
└── content_hash
```

---

# 14. Obsidian Vault Layout

The default proposed layout is:

```text id="xrrtcv"
Atlas Vault/
│
├── 00 Inbox/
│   └── Atlas Captures/
│
├── 10 Projects/
│   └── Project Atlas/
│       ├── Conversations/
│       ├── Decisions/
│       ├── Research/
│       └── Directives/
│
├── 20 Decisions/
│
├── 30 Research/
│
├── 40 Directives/
│
└── 90 Sources/
```

This is a default projection strategy, not a hard architectural dependency.

Users MUST be able to configure routing.

---

# 15. Routing Architecture

Routing should be implemented independently from Markdown rendering.

Conceptually:

```text id="m4j2n0"
RoutingService
    input:
        capture metadata
        project
        classification

    output:
        logical destination
```

Examples:

```text id="egwe8w"
project=atlas
type=conversation
→ 10 Projects/Project Atlas/Conversations/

type=decision
→ 20 Decisions/

unknown
→ 00 Inbox/Atlas Captures/
```

MVP routing SHOULD prioritize explicit information.

Priority:

```text id="z5q5u2"
explicit user project
> deterministic known mapping
> confident classification
> Inbox fallback
```

Never discard content because routing fails.

---

# 16. Markdown Note Schema

A projected note SHOULD have a consistent shape.

Example:

```yaml id="t0y4rv"
---
title: "Atlas Obsidian Integration"
created: "2026-09-05T09:38:00+02:00"
updated: "2026-09-05T09:38:00+02:00"

atlas:
  capture_id: "cap_..."
  source_id: "src_..."
  content_hash: "sha256:..."
  schema_version: 1

source:
  type: "conversation"
  application: "chatgpt"

project:
  - "Project Atlas"

classification:
  - "architecture"

status: "processed"

tags:
  - atlas
  - obsidian
  - capture
---
```

Markdown body:

```markdown id="tscj6x"
# Atlas Obsidian Integration

## Summary

...

## Key Points

...

## Decisions

...

## Actions

...

## Related

- [[Project Atlas]]
- [[AS-OBS-001]]

## Source

Atlas capture: `cap_...`
```

Do not necessarily include the complete raw source body in every note.

The original content is already preserved by Atlas.

A configuration may later permit verbatim projection.

---

# 17. Raw Capture Representation

If Atlas does not already have a canonical format suitable for raw capture, use a versioned schema.

Conceptual example only:

```json id="8hwdlm"
{
  "schema_version": 1,
  "capture_id": "cap_...",
  "source_id": "src_...",
  "project_id": "atlas",
  "source": {
    "type": "conversation",
    "application": "chatgpt"
  },
  "captured_at": "2026-09-05T09:38:00+02:00",
  "content_hash": {
    "algorithm": "sha256",
    "value": "..."
  },
  "content": "...",
  "metadata": {}
}
```

This example does not mandate JSON.

Existing Atlas schemas take precedence.

---

# 18. Lifecycle State Model

Conceptual state machine:

```text id="44tlwn"
RECEIVED
    │
    ▼
VALIDATED
    │
    ▼
PERSISTED
    │
    ├───────────────┐
    ▼               │
PROCESSED           │
    │               │
    ▼               │
RENDERED            │
    │               │
    ▼               │
INGESTED            │
                    │
                FAILED_STAGE
```

A failure should include enough metadata to resume processing.

For example:

```text id="yr6naw"
PERSISTED
OBSIDIAN_WRITE_FAILED
```

is preferable to losing the capture.

---

# 19. Failure Model

Failures should be stage-aware.

Suggested classes:

```text id="nugz2h"
CaptureValidationError
CapturePersistenceError
DuplicateCapture
ClipboardUnavailableError
RoutingError
ObsidianConfigurationError
ObsidianWriteError
IngestError
ProcessingError
```

Existing Atlas error conventions take precedence.

The CLI/API should surface actionable status.

---

# 20. Recovery Architecture

Processing should be resumable.

Conceptual command:

```bash id="x7s3gw"
atlas capture retry <capture-id>
```

or an existing Atlas lifecycle equivalent.

This does not have to be implemented in MVP if repository structure makes it premature, but capture state must make future retries possible.

Potential recovery:

```text id="yf7e4o"
raw persistence succeeded
Obsidian failed

later:

load capture
→ rerender
→ write note
→ ingest
```

---

# 21. CLI Architecture

The CLI is an entry adapter, not the domain implementation.

Conceptual structure:

```text id="1ce7wg"
atlas capture
├── text
└── chat
```

Examples:

```bash id="a7cvon"
atlas capture text "Important information"

atlas capture text --stdin

atlas capture text --clipboard

atlas capture chat --clipboard

atlas capture chat --clipboard --project atlas
```

CLI flow:

```text id="d9etlg"
arguments
    ↓
CLI adapter
    ↓
CaptureRequest
    ↓
CaptureService
    ↓
CaptureResult
    ↓
human-readable output
```

No persistence logic should live only in CLI command handlers.

---

# 22. Clipboard Architecture

Clipboard acquisition SHALL use capability detection.

Conceptual provider interface:

```text id="t3v6xq"
ClipboardProvider
    read_text() -> str
```

Implementations may include:

```text id="w9ihax"
WaylandClipboardProvider
X11ClipboardProvider
NativePythonClipboardProvider
```

Selection strategy:

```text id="p1hrsr"
detect session
    ↓
detect provider availability
    ↓
select provider
    ↓
read clipboard
```

Example:

```text id="jbn14i"
Wayland
    wl-paste available
        -> wl-paste

X11
    xclip available
        -> xclip

fallback
    xsel or existing library

none
    -> actionable error
```

Do not execute arbitrary clipboard contents.

Clipboard content is data only.

---

# 23. Local Capture API

A local API MAY expose the CaptureService.

Recommended endpoint:

```text id="yuehcf"
POST /api/v1/capture
```

Request:

```json id="gs980t"
{
  "source_type": "conversation",
  "source_application": "chatgpt",
  "content": "...",
  "project": "atlas"
}
```

Response:

```json id="zzn1bf"
{
  "capture_id": "cap_...",
  "source_id": "src_...",
  "duplicate": false,
  "state": "ingested",
  "note_path": "10 Projects/Project Atlas/Conversations/..."
}
```

Bind:

```text id="a080f5"
127.0.0.1
```

by default.

Never default to:

```text id="1cgroy"
0.0.0.0
```

---

# 24. API Security Boundary

The capture API accepts untrusted input.

The API SHALL validate:

```text id="pdiq9f"
content type
payload size
source type
metadata structure
project references
requested output modes
```

It SHALL NOT accept arbitrary absolute filesystem destinations.

This is unsafe:

```json id="n9jwkm"
{
  "path": "/etc/..."
}
```

Instead:

```text id="pvi39l"
client specifies logical project/routing information

server resolves destination from trusted configuration
```

---

# 25. Browser Extension Architecture

The browser extension should remain deliberately thin.

```text id="zfmpgk"
Browser Extension
├── selection acquisition
├── minimal source metadata
├── user action
└── localhost POST
```

Atlas owns everything else.

Extension flow:

```text id="df0rj6"
selected content
      │
      ▼
WebExtension
      │
POST localhost
      ▼
Atlas Capture API
```

The extension should not:

* implement dedupe;
* directly manipulate the Obsidian filesystem;
* call Atlas databases;
* perform source registration itself.

---

# 26. Browser Capture Payload

Potential request:

```json id="4e3h6x"
{
  "source_type": "conversation",
  "source_application": "chatgpt",
  "content": "...",
  "source_metadata": {
    "page_title": "...",
    "source_url": "..."
  },
  "project": "atlas"
}
```

URL retention should be configurable if privacy concerns warrant it.

Authentication/session tokens MUST NOT be captured.

---

# 27. Atlas Ingestion Integration

Generated knowledge should eventually enter the existing Atlas source lifecycle.

Preferred integration:

```text id="ytj9fx"
CaptureService
    ↓
existing Atlas source registration API
    ↓
existing ingest API
    ↓
existing index/query pipeline
```

Avoid:

```text id="7t3wtq"
subprocess("atlas ingest ...")
```

where a stable internal API exists.

Shelling out is acceptable only if the repository currently establishes CLI invocation as the canonical integration boundary.

---

# 28. Ingestion Source Strategy

There are two possible models.

Repository truth should determine which one aligns with Atlas.

## Model A — Raw capture is the Atlas source

```text id="yl6wiw"
RawCapture
    = Atlas source

Obsidian note
    = derived representation
```

Advantages:

* strongest provenance;
* raw evidence is canonical.

---

## Model B — Curated Markdown is also a registered source

```text id="0zqw6a"
RawCapture
    = capture evidence

MarkdownNote
    = derived Atlas source
```

Advantages:

* easy ingestion using existing Markdown pipeline.

Potential downside:

* duplicate semantic representation.

If Model B is used, lineage must explicitly record:

```text id="3yrg9c"
MarkdownSource derived_from RawCapture
```

---

# 29. Preferred Ingestion Model

Where Atlas supports it, prefer:

```text id="gjwh9e"
RAW CAPTURE
    │
    ├── authoritative evidence
    │
    ▼
CURATED NOTE
    │
    ├── derived human representation
    │
    ▼
KNOWLEDGE INDEX
```

This preserves the distinction between evidence and interpretation.

---

# 30. Configuration Architecture

Use existing Atlas configuration mechanics.

Conceptual section:

```yaml id="nsen33"
obsidian:
  enabled: true

  vault_path: "/home/user/Documents/Obsidian/Atlas"

  routing:
    inbox: "00 Inbox/Atlas Captures"
    projects: "10 Projects"
    decisions: "20 Decisions"
    research: "30 Research"
    directives: "40 Directives"
    sources: "90 Sources"

capture:
  deduplication: true
  default_source_application: "unknown"

  clipboard:
    enabled: true

  processing:
    ai_enrichment: false
```

The exact schema SHALL be aligned with Atlas config conventions.

---

# 31. Configuration Precedence

Where consistent with Atlas:

```text id="o7z4z4"
CLI argument
    >
environment override
    >
project configuration
    >
user configuration
    >
default
```

Do not introduce new precedence behavior if Atlas already defines one.

---

# 32. Filesystem Safety

All Obsidian writes MUST resolve under the configured vault root.

Conceptual invariant:

```text id="wql2fb"
resolved_target.is_relative_to(resolved_vault_root)
```

Reject traversal patterns and resolved escapes.

Threats include:

```text id="gpy193"
../outside.md

../../etc/passwd

symlink-to-outside/

absolute path injection
```

Where practical, validate after resolution.

---

# 33. Filename Strategy

Filename generation should be deterministic enough to remain readable but collision-safe.

Suggested pattern:

```text id="9rot6f"
YYYY-MM-DD-slug.md
```

Collision handling:

```text id="7v9t05"
YYYY-MM-DD-slug.md
YYYY-MM-DD-slug-2.md
```

or ID suffix:

```text id="yjl8t1"
YYYY-MM-DD-slug-cap_01KXYZ.md
```

Do not rely solely on title uniqueness.

---

# 34. Atomic Writes

Prefer:

```text id="j9qg0q"
write temporary file
fsync if appropriate
atomic rename
```

where existing Atlas filesystem utilities permit.

This prevents partially written notes if the process terminates during rendering.

---

# 35. Frontmatter Serialization

Use a real YAML serializer.

Do not generate YAML via unsafe string concatenation.

Correct conceptual approach:

```text id="pdzaha"
metadata object
    ↓
safe YAML serializer
    ↓
frontmatter
```

Test strings containing:

```text id="j650l9"
:
---
"
'
[
]
#
newline
unicode
```

---

# 36. Logging

Logging SHALL record operational metadata without routinely logging raw capture contents.

Safe example:

```text id="mh7z4k"
capture persisted id=cap_... bytes=12842 source=chatgpt
```

Avoid:

```text id="giqu3z"
capture content="entire private conversation ..."
```

Debug-level content logging should be avoided unless explicitly designed and documented.

---

# 37. Privacy Architecture

Raw capture content may contain:

* personal notes;
* credentials pasted accidentally;
* code;
* conversations;
* business information;
* project secrets.

Therefore:

```text id="wbxxea"
local persistence
    = allowed

external transmission
    = opt-in only
```

Any AI processor that invokes an external provider SHALL expose that fact.

Future configuration could define:

```yaml id="34sgwk"
processing:
  external_ai:
    enabled: false
```

Default SHOULD remain off unless Atlas already has a user-controlled AI execution policy.

---

# 38. Secrets Handling

AS-OBS-001 SHOULD NOT attempt aggressive secret scanning or redaction in MVP because changing captured content would violate raw-evidence preservation.

Instead:

```text id="xb52up"
raw capture
    remains original

derived projection
    may later support configurable redaction
```

Potential future feature:

```text id="fqcsh9"
rendered_note_redaction = enabled
```

while original source remains intact under explicit local storage policy.

---

# 39. Temporal Semantics

A capture may contain information describing another point in time.

Do not conflate:

```text id="xawjsa"
captured_at
```

with:

```text id="d67mbk"
valid_at
event_time
source_document_time
conversation_time
```

AS-OBS-001 SHALL preserve capture time.

Where existing Atlas temporal semantics support document/source time, reuse them.

Future conversational ingestion may extract per-message timestamps.

---

# 40. Authority Semantics

Conversation captures are not automatically authoritative facts.

A captured ChatGPT message represents:

```text id="nkan1q"
a source artifact
```

not necessarily:

```text id="ygoh4f"
ground truth
```

Existing Atlas authority/domain authority mechanisms SHOULD remain applicable.

AS-OBS-001 SHALL NOT assign high factual authority solely because a message came from an LLM.

---

# 41. Conversation-Level Model

Future ChatGPT capture may include multiple messages.

Architecture should permit:

```text id="56h80z"
ConversationCapture
├── conversation_id?
├── title?
├── captured_at
└── messages[]
```

Each message could eventually include:

```text id="ffrzwt"
message_id
role
timestamp?
content
model?
source metadata
```

AS-OBS-001 MVP may initially store selected conversation content as a single raw text capture.

Do not prematurely require message-level parsing.

---

# 42. Knowledge Graph Integration

Future AS-OBS-002 processors may identify relationships such as:

```text id="vkr1a2"
Capture
    mentions → AS-OBS-001

Capture
    references → PR-654

Decision
    relates_to → DOGFOOD-001

Directive
    supersedes → prior directive
```

Therefore processed metadata should permit arbitrary typed relationships.

Conceptual form:

```text id="z4hio7"
Relation
├── source_entity
├── relation_type
├── target_entity
└── confidence
```

Do not require this graph model in MVP if Atlas already supplies another relationship mechanism.

---

# 43. Obsidian Wikilink Architecture

Wikilinks are presentation helpers.

They must not become Atlas' canonical identity system.

For example:

```text id="d0ncjj"
[[AS-OBS-001]]
```

is human-facing syntax.

Atlas entity identity should remain independently represented.

Conceptual mapping:

```text id="h1jr6s"
Atlas entity ID
    ↔
Obsidian note/wiki label
```

---

# 44. Note Mutation Policy

AS-OBS-001 SHOULD default to creating derived notes rather than editing arbitrary user-authored notes.

Future merge behavior must distinguish:

```text id="v5jcqy"
Atlas-managed note
user-managed note
mixed note
```

Recommended future frontmatter:

```yaml id="e92x7p"
atlas:
  managed: true
```

This can establish whether Atlas may regenerate content.

---

# 45. Managed vs Unmanaged Content

Future Atlas-generated notes may use explicit managed regions.

Example:

```markdown id="7cgl3c"
<!-- atlas:managed:start -->

Generated content...

<!-- atlas:managed:end -->
```

User-authored regions can remain untouched.

This is not mandatory in AS-OBS-001 but the architecture SHOULD avoid making future safe regeneration impossible.

---

# 46. Versioning

Persisted schemas SHALL be versioned.

Potential versions:

```text id="h0mueb"
capture_schema_version
note_schema_version
processor_version
```

This allows future migrations without guessing format.

Do not version every internal class unnecessarily.

Version durable serialized contracts.

---

# 47. Compatibility

AS-OBS-001 SHALL preserve:

* existing Atlas CLI behavior;
* existing source identity behavior;
* existing ingestion semantics;
* existing query semantics;
* existing configuration compatibility;
* existing test guarantees.

Any schema migration introduced by AS-OBS-001 must be explicit and tested.

---

# 48. Performance

Typical captures are expected to be relatively small.

MVP SHOULD optimize for correctness and reliability over micro-optimization.

However:

* avoid repeatedly indexing the entire vault for one capture;
* avoid loading all historical captures to test a hash if an index exists;
* avoid unnecessary external model calls;
* avoid spawning excessive subprocesses.

Deduplication lookup should preferably be indexed.

---

# 49. Concurrency

Two capture requests may arrive simultaneously.

Potential scenario:

```text id="9ij32p"
request A hash = X
request B hash = X
```

Both must not create independent duplicates due to a race.

Where Atlas already has per-project or source locking, reuse it.

Otherwise dedupe persistence must be transactionally or atomically guarded.

This should be covered by tests if concurrent capture is supported.

---

# 50. CLI Result Contract

Human-readable output should be compact and explicit.

Example:

```text id="xg6m0g"
Atlas Capture

Capture ID : cap_01K...
Source ID  : src_01K...
Type       : conversation
Application: chatgpt
Project    : Project Atlas
Duplicate  : no

Raw        : persisted
Obsidian   : written
Atlas      : ingested

Note:
10 Projects/Project Atlas/Conversations/
2026-09-05-atlas-obsidian-integration.md
```

For duplicate:

```text id="q999ju"
Duplicate capture detected.

Capture ID : cap_01K...
Hash       : sha256:...

No duplicate note created.
```

---

# 51. Machine Result Contract

Internal consumers should receive structured results.

Conceptual schema:

```text id="o3lzd7"
CaptureResult
├── capture_id
├── source_id?
├── duplicate
├── existing_capture_id?
├── lifecycle_state
├── content_hash
├── outputs[]
├── errors[]
└── warnings[]
```

This same result can power:

* CLI;
* REST API;
* browser extension;
* future GUI.

---

# 52. API Versioning

Use versioned API routes.

Preferred:

```text id="eqclfq"
POST /api/v1/capture
```

Future incompatible changes can introduce:

```text id="pnax5b"
/api/v2/
```

Avoid exposing internal database models directly as API contracts.

---

# 53. Dependency Direction

Preferred dependency direction:

```text id="m5plh5"
CLI ───────────────┐
API ───────────────┤
Browser Adapter ───┤
                   ▼
              CaptureService
                   │
                   ▼
               Domain
             ┌─────┴─────┐
             ▼           ▼
      CaptureStore   Processors
                         │
                         ▼
                   OutputAdapters
                         │
                         ▼
                       Atlas
```

Domain code SHALL NOT depend on CLI or browser code.

Obsidian adapter SHALL NOT own source acquisition.

---

# 54. Proposed Logical Package Boundaries

Only if compatible with repository structure, a possible arrangement is:

```text id="oxv6mt"
atlas/
├── capture/
│   ├── models
│   ├── service
│   ├── repository
│   ├── dedupe
│   ├── processing
│   ├── routing
│   │
│   ├── sources/
│   │   ├── clipboard
│   │   └── stdin
│   │
│   └── outputs/
│       └── obsidian
│
├── cli/
│   └── capture
│
└── api/
    └── capture
```

Do not impose this tree if Atlas already has clearly established layer boundaries.

---

# 55. Extension Points

The architecture should expose stable seams.

## Source extension

```text id="53l47n"
new SourceAdapter
```

## Processing extension

```text id="j73nmz"
new KnowledgeProcessor
```

## Routing extension

```text id="io18gc"
new RoutingPolicy
```

## Output extension

```text id="m0zq05"
new OutputAdapter
```

## Ingestion extension

```text id="jhq7vt"
new Atlas ingestion bridge
```

This is preferable to growing a single monolithic capture command.

---

# 56. Future AS-OBS-002 Architecture

AS-OBS-002 may add:

```text id="wuia3e"
ConversationIntelligencePipeline
├── segmentation
├── summarization
├── decision extraction
├── action extraction
├── entity resolution
├── relation extraction
├── contradiction detection
├── supersession detection
├── semantic linking
├── note consolidation
└── project timeline updates
```

These should consume AS-OBS-001 CaptureRecords.

AS-OBS-002 must not require migration of the original capture model if AS-OBS-001 is designed correctly.

---

# 57. Future Browser Workflow

Desired final UX:

```text id="v6ri0h"
ChatGPT
   │
   ├── select assistant message
   │
   ├── right-click
   │
   └── Send to Atlas
            │
            ▼
      localhost API
            │
            ▼
       CaptureService
            │
            ├── raw persistence
            ├── dedupe
            ├── provenance
            ├── enrichment
            ├── Obsidian
            └── Atlas index
```

Possible extension actions:

```text id="ztbey0"
Send to Atlas
Send verbatim
Create decision
Create research note
Create directive
Add to Project Atlas
```

They should map to CaptureRequest options, not independent workflows.

---

# 58. Future Whole-Conversation Capture

Eventually Atlas may support:

```text id="5mwboe"
Capture conversation
```

instead of only selected text.

Potential processing:

```text id="6uboxp"
conversation
    ↓
message segmentation
    ↓
turn classification
    ↓
important knowledge extraction
    ↓
multiple derived notes
```

One raw conversation may yield multiple knowledge artifacts.

Therefore:

```text id="ylts16"
1 CaptureRecord
→ N DerivedArtifacts
```

must be allowed.

---

# 59. Derived Artifact Model

Conceptual:

```text id="6euqwt"
DerivedArtifact
├── artifact_id
├── capture_id
├── artifact_type
├── generated_at
├── processor
├── content_hash
├── path?
└── metadata
```

Artifact types may include:

```text id="jo6h8k"
obsidian_note
summary
decision
directive
task_set
entity_graph
```

This is a useful abstraction if Atlas lacks an equivalent existing model.

---

# 60. Traceability Example

An end-to-end trace should be possible.

Example:

```text id="yw7wni"
User selected ChatGPT message

    ↓

Capture ID:
cap_123

    ↓

Atlas Source ID:
src_987

    ↓

Content hash:
sha256:abc...

    ↓

Derived artifact:
art_456

    ↓

Obsidian note:
10 Projects/Project Atlas/Conversations/
2026-09-05-atlas-obsidian-integration.md

    ↓

Atlas indexed source:
knowledge/source/...

    ↓

atlas query "Obsidian integration"
```

Every derived stage should point backwards.

---

# 61. Testing Architecture

Tests should follow component boundaries.

Suggested groups:

```text id="1tfprt"
unit/
├── capture_identity
├── dedupe
├── routing
├── markdown_rendering
├── path_safety
└── clipboard_provider

integration/
├── capture_to_store
├── capture_to_obsidian
├── capture_to_ingest
├── duplicate_capture
└── failure_recovery

api/
├── capture_success
├── validation
├── request_limits
└── path_injection

cli/
├── stdin
├── clipboard_mock
├── project_routing
└── duplicate_status
```

Use repository-native testing layout.

---

# 62. Required Architectural Tests

At minimum verify these invariants.

### Raw source survives rendering failure

```text id="l5zyhg"
capture
→ persist succeeds
→ Obsidian write fails
→ raw capture still exists
```

### Duplicate protection

```text id="uk0lag"
capture A
capture A again
→ one logical persisted content object
→ no uncontrolled note duplication
```

### Path traversal protection

```text id="25meou"
routing value = ../../outside
→ rejected
```

### Offline operation

```text id="h6zxdx"
no AI credentials
→ deterministic capture succeeds
```

### Unicode

```text id="65ippn"
Dutch
emoji
code blocks
special characters
→ preserved
```

### Provenance

```text id="ppmwze"
Obsidian note capture_id
→ resolves to persisted capture
```

---

# 63. Observability

Useful metrics/events may include:

```text id="d9kkfd"
capture_received
capture_persisted
capture_duplicate
capture_processed
obsidian_written
obsidian_failed
atlas_ingested
atlas_ingest_failed
```

Do not build a heavy metrics stack solely for this feature.

Reuse existing Atlas observability.

---

# 64. Security Threat Model

## Threat: path traversal

Mitigation:

* trusted routing;
* canonical path resolution;
* vault-root containment checks.

## Threat: arbitrary code execution

Mitigation:

* treat captured content as data;
* never shell-evaluate content;
* subprocess arguments are fixed.

## Threat: network exposure

Mitigation:

* loopback-only API default.

## Threat: sensitive content leakage

Mitigation:

* local-first;
* external AI disabled or explicit;
* content omitted from routine logs.

## Threat: malicious Markdown/YAML

Mitigation:

* safe serialization;
* avoid arbitrary plugin execution;
* preserve as text.

## Threat: symlink escape

Mitigation:

* resolved-path checks where practical.

## Threat: duplicate race

Mitigation:

* atomic/transactional identity registration.

---

# 65. Architectural Decision Records

The implementation SHOULD document material choices as ADRs if Atlas already uses ADRs.

Candidate ADRs:

```text id="4komhd"
ADR — Atlas owns canonical capture evidence

ADR — Obsidian is an output projection

ADR — Capture pipeline is deterministic-first

ADR — Local capture API binds only to loopback

ADR — CaptureService is shared by CLI/API/extensions
```

Do not introduce an ADR framework if the repository has none unless justified.

---

# 66. Architecture Acceptance Criteria

Architecture is considered correctly implemented when:

### Source acquisition

```text id="b6ezg8"
clipboard/stdin/text
→ same CaptureService
```

### Canonical preservation

```text id="cwui38"
accepted capture
→ recoverable original content
```

### Stable identity

```text id="ztxyr7"
content
→ deterministic hash
```

### Deduplication

```text id="zexotg"
same content twice
→ duplicate recognized
```

### Projection

```text id="a38dz7"
capture
→ Obsidian-compatible Markdown
```

### Provenance

```text id="d756ji"
note
→ capture
→ source
```

### Atlas integration

```text id="qzbt7u"
capture/note
→ existing source lifecycle
→ queryable or correctly ingest-ready
```

### Failure isolation

```text id="rhe1d1"
optional stage fails
→ raw evidence survives
```

### Offline functionality

```text id="mm3lya"
no external model available
→ capture still works
```

### Extension readiness

```text id="980fet"
future browser extension
→ requires only API adapter
→ no architecture rewrite
```

---

# 67. Architectural North Star

AS-OBS-001 should establish Atlas as a universal knowledge acquisition layer.

The long-term architecture is:

```text id="hckgj1"
               INFORMATION SOURCES

 ChatGPT   Claude   Codex   Kimi   GitHub
 Terminal  Email    Web     PDF    Files
      │       │       │      │       │
      └───────┴───────┴──────┴───────┘
                      │
                      ▼
             ┌─────────────────┐
             │  Atlas Capture  │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │ Atlas Provenance│
             │ & Source Lineage│
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │ Knowledge Layer │
             │                 │
             │ classify        │
             │ summarize       │
             │ relate          │
             │ temporalize     │
             │ validate        │
             │ reconcile       │
             └────────┬────────┘
                      │
            ┌─────────┴──────────┐
            │                    │
            ▼                    ▼
       Obsidian              Atlas Query
       Human UI               Machine UI
```

Atlas therefore becomes the bridge between:

```text id="t5rcqo"
ephemeral information
```

and:

```text id="0zbhtj"
durable knowledge
```

---

# 68. Final Principle

The implementation must preserve this ordering:

```text id="nd8loq"
PRESERVE FIRST
UNDERSTAND SECOND
PRESENT THIRD
```

Never:

```text id="kz4wqi"
summarize first
discard original
store only interpretation
```

The primary invariant remains:

> Never sacrifice original source evidence for a convenient generated note.

AS-OBS-001 should make conversational knowledge effortless to capture today while establishing an extensible acquisition architecture for the broader Atlas knowledge system tomorrow.
