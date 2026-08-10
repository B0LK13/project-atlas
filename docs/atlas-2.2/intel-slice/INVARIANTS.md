# Intelligence slice — hard invariants (PREP)

Package: **AS-2.2-INTEL-SLICE-PREP-001** (base) + **AS-2.2-INTEL-SLICE-DEEPEN-PREP-001** (deepen notes)  
Status: **normative for this PREP tree**; runtime enforcement deferred until unlock.

## 1. Slice ≠ authority

| Signal | Allowed | Forbidden |
|---|---|---|
| Envelope authority | `authority.level = derived` | `canonical` / elevated levels |
| Upstream fusion ranks | Cite as derived inputs | Stamp Layer B claims |
| LLM narrative | Optional explanation cite | Authority / trust score |

Truth boundary:  
`INTEL SLICE ≠ AUTHORITY / ≠ LAYER B WRITE`

## 2. Composition ≠ mutation

| Surface | May do | Must not do |
|---|---|---|
| Intelligence slice | Cite KF / RET / TEMPORAL / CONFLICT ids | Write those emit trees |
| Ask / MCP / UI lens | Render slice | `_promote` / canonical vault write |
| Fixture rehearsal | Assert envelope shape | Mutate `src/` runtime |

This PREP lane **must not** edit runtime under `src/`, `apps/`, `api_server`,
or `mcp_server`.

## 3. No silent conflict resolve

| Signal | Allowed | Forbidden |
|---|---|---|
| Open conflict citation | Retain in `inputs.conflicts[]` / `unknown[]` | Drop / invent winner |
| Operator disposition | Escalate / open evidence (post-unlock) | `auto_resolve` / LLM pick |
| Missing temporal window | `unknown` | Invented validity |

## 4. LLM ≠ authority / UI ≠ canonical

| Field | Const / rule |
|---|---|
| `authority.level` | `derived` |
| `canonical_write` | `false` |
| Subjective confidence / trust | **forbidden** (objective signals only) |
| LLM-suggested winner | rejected (`llm_authority` / `silent_conflict_resolve`) |

## 5. Certification / unlock wall

| Field | Const / rule |
|---|---|
| `pilot_roots` | `0` |
| `authentic_estate` | `false` on fixtures |
| `evidence_class` | `fixture-only` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

Fixture slice rehearsal ≠ authentic estate PILOT PASSED ≠ 2.1 RELEASE
CERTIFIED ≠ 2.2 unlock.

## 6. Deepen notes (AS-2.2-INTEL-SLICE-DEEPEN-PREP-001)

Additive fail-closed vocabulary for certification walls. Base negatives
(authority-elevation / silent-conflict-resolve / llm-authority /
canonical-write) remain owned by `AS-2.2-INTEL-SLICE-PREP-001` informal expect
JSON — **do not relocate**.

| Forbidden kind | Const / rule |
|---|---|
| `release_cert_stamp` | Slice / DEMO VERIFIED must not stamp `ATLAS_2_1_RELEASE_CERTIFIED` |
| `pilot_invent` | `pilot_roots=0`, `authentic_estate=false`, `pilot_pass=false` |
| `llm_authority_stamp` | LLM prose never stamps winners or elevates authority |

Deepen negative payloads **must** carry:

| Field | Const |
|---|---|
| `evidence_class` | `fixture-only` |
| `authentic_estate` | `false` |
| `release_certified` | `false` |
| `pilot_pass` | `false` |
| `canonical_writes` | `false` |
| `status` | `rejected_forbidden` |

Truth boundary (deepen):  
`INTEL SLICE ACTION ≠ RELEASE CERT / ≠ PILOT PASS / ≠ LLM AUTHORITY / ≠ CANONICAL WRITE`

**DEMO VERIFIED ≠ release / PILOT.** Any demo or fixture walkthrough grants no
release, WEB ACCEPTED, authentic-estate PILOT, or unlock credit.
