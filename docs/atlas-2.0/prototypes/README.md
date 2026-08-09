# Atlas 2.0 — Prototypes (non-production)

Status: **PROTOTYPE / PREP ONLY** — `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

This directory holds **non-production** prototype stubs for Atlas 2.0 Track B
prep. Nothing here is a shippable product surface, CLI command, schema, or
runtime dependency.

## Non-production markers

| Marker | Meaning |
|---|---|
| **PROTOTYPE** | Sketch / stub; may change without compatibility obligation |
| **NON-PRODUCTION** | Must not be wired into `src/`, CI production gates, or package data |
| **READY=NO** | Does not contribute evidence toward IMPLEMENTATION READY flip |

## Rules

1. Prototypes under this tree are **docs-only** unless a future governor
   explicitly authorizes a production package (after READY=YES).
2. Titles and headers must retain `PROTOTYPE` / `NON-PRODUCTION` markers.
3. Do not import, vend, or ship these stubs as dependency-bearing schemas.
4. Do not treat prototype filenames as reserved production CLI verbs.
5. Parent inventory: [PROTOTYPE-MARKERS.md](../PROTOTYPE-MARKERS.md).

## Current stubs

| Path | Marker | Notes |
|---|---|---|
| `prototypes/README.md` | PROTOTYPE / NON-PRODUCTION | This index; deepen-e placeholder |

Additional prototype files may be added later under this directory. Each new
file must carry an explicit non-production header and remain `READY=NO`.

## Explicit firewall

- No production semantics in `src/project_atlas/` from these stubs.
- No production MCP/SDK wiring from prototype sketches.
- `ATLAS_2_0_IMPLEMENTATION_READY = NO` always for this directory until
  a governor flips the §56 / §101 gate elsewhere — **never** from here.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | deepen-e: initial prototypes stub README (non-production) |
