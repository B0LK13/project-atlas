# AS-CORE-002 source-lifecycle erratum

**Status:** `AS-CORE-002 CERTIFICATION REOPENED — REMEDIATION IN PROGRESS`  
**Hotfix branch:** `fix/source-lifecycle-replay`  
**Original certified main:** `46c739c`

## Defect

The original ingestion implementation stored source-observation values such
as `modified`, `deleted`, and `restored-elsewhere` in
`SourceLifecycleRecord.lifecycle`. That field is a `DocumentLifecycle` and
does not admit source-change observations. A deletion therefore produced a
state file that could be written successfully but could not be validated on a
subsequent unchanged ingest.

## Why prior testing missed it

AS-CORE-002 tested deletion retention and ordinary unchanged replay
separately, but did not execute deletion followed by an immediate unchanged
ingest against the persisted tombstone. The invalid value crossed the write
boundary before the next validation exposed it.

## Correction

`SourceLifecycleRecord` now separates `document_lifecycle` from
`source_change_state`. The latter explicitly supports `new`, `unchanged`,
`modified`, `deleted`, `restored`, `restored-elsewhere`, and `renamed`.

Known legacy lifecycle values are repaired only during an explicit, versioned
compatibility path. The repair preserves IDs, hashes, timestamps and history,
marks the repaired records, and emits a receipt under
`receipts/source-lifecycle/`. Unknown values and schema versions fail closed.

## Recertification scope

The hotfix must prove deletion/no-op replay, modification stability,
same-path and changed-content restoration, rename detection, legacy repair,
unknown-value rejection, transaction rollback, strict validation and the full
Core/Control Plane/repository suites. Independent Agent Two verification is
required before certification is restored.
