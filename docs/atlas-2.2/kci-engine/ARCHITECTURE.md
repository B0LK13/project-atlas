# PREP — Knowledge CI engine architecture

Status: **PREP / NON-NORMATIVE DRAFT**. Not a public API freeze.
Package: `AS-2.2-KCI-ENGINE-PREP-001`.

Tip pin: MAIN `f45134f` / TREE `02eeb739`. Evidence:
`D:\project-atlas-orphans\atlas-2.1-productionization-001\`
(`AS-COORD-CYCLE-2.1-011`, board empty-except-PILOT).

---

## 1. Problem statement

Atlas 2.0 shipped:

1. **Thin KCI envelopes** (`AS-2.0-KCI-001`) — consume-only compile request /
   receipt JSON under `generated/kci/`.
2. **Gate catalog harness** (`AS-2.0-KCI-HARNESS-001`) — lists schema / pytest /
   ruff / mypy / compat gates with `authority_promoted=false`.

Neither surface **evaluates** knowledge units against vault evidence, nor
produces a deterministic suite report that Agent OS / UX can consume without
risking silent Layer B promotion. Atlas 2.2 (post-`v2.1.0`) needs an
**engine** that turns knowledge assertions into fail-closed CI outcomes while
preserving 1.0/2.1 authority invariants.

Gap register: **GAP-NS-005** → proposed package `AS-2.2-KCI-001`.

---

## 2. Design intent (engine, not catalog)

| Concern | 2.0 harness today | 2.2 engine (target after unlock) |
|---|---|---|
| Input | Gate list + fixture mode | Knowledge unit suite + vault snapshot refs |
| Work | Emit catalog receipt | Deterministic evaluate → suite report |
| Authority | Hard-forbid promote | Hard-forbid promote + refuse silent winners |
| Output path | `generated/ops/kci/` | `generated/kci/engine/` (proposed; not created here) |
| Evidence class | FIXTURE | FIXTURE → BOUNDED → LIVE_READ_ONLY (never Layer B) |

---

## 3. Proposed layers

```text
┌─────────────────────────────────────────────────────────────┐
│  Suite authoring (human / Agent OS)                         │
│  knowledge unit specs (see UNIT-TEST-LANGUAGE.md)           │
└────────────────────────────┬────────────────────────────────┘
                             │ suite_ref + vault_pin
                             v
┌─────────────────────────────────────────────────────────────┐
│  KCI Engine (read-only evaluator)                           │
│  1. load suite (fail-closed schema)                         │
│  2. resolve evidence refs via query / indexes (consume-only)│
│  3. evaluate assertions (exact / presence / conflict-safe)  │
│  4. emit suite report + per-unit outcomes                   │
│  5. NEVER write Layer B / NEVER change authority winners    │
└────────────────────────────┬────────────────────────────────┘
                             │ report (consume_only=true)
                             v
┌─────────────────────────────────────────────────────────────┐
│  Consumers (post-unlock)                                    │
│  CI gate · Agent OS session · UX ops lens · ADV matrices    │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 Authoring layer

- Knowledge units are declarative YAML/JSON sketches (language draft only now).
- Units reference **subject / claim / source / conflict** IDs — never raw
  model prose as authority.
- Suites are versioned; digest of suite body is recorded on the report.

### 3.2 Evaluator layer (future runtime)

- Pure functions over vault read APIs / generated indexes.
- Deterministic: sorted keys, stable ID ordering, no wall-clock in reports
  (NFR-001 carry-forward).
- Fail-closed on: missing pin, schema drift, ambiguous subject, secret findings
  metadata requiring quarantine, promote flags.

### 3.3 Report layer

Proposed report envelope fields (sketch; **not** a shipped schema):

| Field | Const / rule |
|---|---|
| `package_id` | future `AS-2.2-KCI-001` |
| `compat_snapshot_id` | pin to `v2.1.0` anchor after COMPAT-PIN |
| `consume_only` | `true` |
| `authority_promoted` | `false` |
| `truth_boundary` | `KCI ENGINE REPORT ≠ LAYER B AUTHORITY` |
| `suite_digest` | SHA-256 of canonical suite bytes |
| `outcomes[]` | per-unit `pass` / `fail` / `error` / `skip` |

---

## 4. Truth boundaries (normative for PREP)

| Boundary | Meaning |
|---|---|
| `KCI COMPILE ≠ AUTHORITY / ≠ SILENT WINNER` | Carry from `AS-2.0-KCI-001` |
| `KCI RECEIPT ≠ LAYER B AUTHORITY` | Carry from compile receipt |
| `KNOWLEDGE CI HARNESS ≠ AUTHORITY PROMOTE` | Carry from harness |
| `KCI ENGINE REPORT ≠ LAYER B AUTHORITY` | New for engine reports |
| `KCI UNIT PASS ≠ CLAIM CERTIFIED` | Unit pass is derived evidence only |
| `KCI SUITE GREEN ≠ ESTATE PILOT PASS` | Never substitutes authentic PILOT |

---

## 5. Integration sketch (post-unlock only)

| Peer package | Interaction |
|---|---|
| `AS-2.2-COMPAT-PIN-001` | Engine refuses run without 2.1 compat pin |
| `AS-2.2-RET-CTX-001` | Optional evidence resolution via hybrid retrieval |
| `AS-2.2-TEMPORAL-001` | Validity-window assertions in units |
| `AS-2.2-CONFLICT-UX-001` | Conflict-presence / review-queue assertions |
| `AS-2.2-KF2-FABRIC-001` | Estate inventory refs for multi-project suites |
| 2.1 live API / MCP | Read-only consumers of reports; no write-back |

---

## 6. Threat notes (prep)

| Threat ID (sketch) | Abuse | Mitigation |
|---|---|---|
| T-2.2-KCI-001 | Suite that auto-promotes winners | `authority_promoted` const false; refuse promote kwargs |
| T-2.2-KCI-002 | Model output cited as unit oracle | Units may only cite vault refs / digests |
| T-2.2-KCI-003 | Green suite used as PILOT evidence | Explicit evidence-class field; PILOT gate rejects KCI class |
| T-2.2-KCI-004 | Path traversal via suite refs | Vault-relative refs; `is_relative_to` checks (AT-013) |
| T-2.2-KCI-005 | Non-determinism / flaky CI | Sorted outcomes; no timestamps; fixture_mode default |

Full ADV rows deferred to `AS-2.2-ADV-POOL-001` (docs/tests only until unlock).

---

## 7. Implementation readiness (all NO)

| Gate | Value |
|---|---|
| Contract freeze | **NO** |
| Schema shipped | **NO** |
| Runtime module | **NO** |
| CI job | **NO** |
| `AS-2.2-KCI-001` READY | **NO** |
| Production mutation this PREP | **NO** |

---

## 8. Cross-links

- Strategy: `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`
- Gap: `docs/strategy/ATLAS-GAP-REGISTER.md` · GAP-NS-005
- 2.0 KCI: `docs/AS-2.0-KCI-001.md`, `docs/AS-2.0-KCI-HARNESS-001.md`, `docs/atlas-2.0/KCI.md`
- Unit-test language: [UNIT-TEST-LANGUAGE.md](UNIT-TEST-LANGUAGE.md)
- Fixtures: [FIXTURE-PLAN.md](FIXTURE-PLAN.md)

`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO`.
