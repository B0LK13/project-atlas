# Atlas 2.2 — Live Reality Gap collectors (lane)

| Field | Value |
|---|---|
| Package | `AS-2.2-REALITY-LIVE-001` |
| Lane | `docs/atlas-2.2/reality-live/` |
| Mode | **PREP only** (pre-`v2.1.0`) |
| Sole-writer surface | This directory + `docs/atlas-2.2/contracts/reality-live/` + prep test |

## Contents

| Doc / path | Role |
|---|---|
| [COLLECTORS-DESIGN.md](COLLECTORS-DESIGN.md) | Collector architecture, I/O, fail-closed rules |
| [PLANES.md](PLANES.md) | Conversational / documentary / implementation / operational planes |
| [fixtures/](fixtures/) | Deterministic fixture corpora (evidence_class=`fixture-only`) |
| [../contracts/reality-live/](../contracts/reality-live/) | Draft JSON schemas (not shipped in `src/` yet) |
| [../../AS-2.2-REALITY-LIVE-001.md](../../AS-2.2-REALITY-LIVE-001.md) | Package card |

## Why this lane exists

`AS-2.0-REALITY-GAP-001` inventories **named theme gaps** (estate twin, SYNC,
provider/MCP, …). Live Reality Gap collectors instead ask, per plane:

> Does observable evidence support what the package board / maturity matrix
> claims right now?

That keeps Track B / 2.2 honesty independent of marketing package names.

## Safety

- No production module mutation in PREP
- No PILOT root invent
- No RELEASE / WEB ACCEPTED / cert stamps from fixture success
