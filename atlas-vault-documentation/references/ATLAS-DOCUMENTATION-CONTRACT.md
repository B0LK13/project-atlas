# Atlas Documentation Contract

## Objective

Make project documentation part of execution rather than reconstructing it from memory after the fact.

## Transaction model

Each meaningful event progresses through:

```text
captured
normalized
routed
validated
acknowledged
```

A transaction may also be `pending`, `blocked`, or `failed`.

## Minimum durable state

`captured` is the immediate minimum. It requires an atomic raw event file with a stable ID and occurrence time.

## Clean completion state

Clean completion requires:

```text
captured + normalized + routed + validated + acknowledged
```

Pending normalization is acceptable only when the raw event is safe, the reason is recorded, no unsupported canonical claim was made, and the receipt reports the pending state.

## Event ID

Recommended format:

```text
AE-YYYYMMDDTHHMMSSZ-<project-slug>-<short-hash>
```

## Required targets

Every event:

- raw source event;
- normalized event;
- project log entry.

Conditional targets:

- project status;
- work package;
- decision;
- validation;
- risk;
- issue/finding;
- component;
- architecture;
- roadmap;
- deployment;
- environment;
- release;
- context pack.

## Atomicity and idempotency

Raw capture is atomic. Reprocessing the same event preserves its ID, creates no duplicate log entries, duplicates no evidence, updates only generated regions, and preserves human regions.

## Auditability

Each normalized event identifies the raw source, normalizer and skill, generation time, project and work package, affected concepts, and validation state.
