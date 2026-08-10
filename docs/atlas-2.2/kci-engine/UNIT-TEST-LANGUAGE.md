# PREP — Knowledge unit-test language (draft)

Status: **PREP / LANGUAGE DRAFT ONLY**. Not executable. Not a schema freeze.
Package: `AS-2.2-KCI-ENGINE-PREP-001`.

---

## 1. Goals

Define a small, deterministic vocabulary for **knowledge units** — assertions
about vault evidence that a future KCI engine can evaluate without promoting
Layer B authority.

Inspired by software unit tests, but the oracle is **source-backed vault
state**, never LLM judgment.

---

## 2. Core nouns

| Term | Meaning |
|---|---|
| **Knowledge unit** | One named assertion with inputs, expect, and evidence class |
| **Suite** | Ordered collection of knowledge units + suite metadata |
| **Subject ref** | Stable subject / concept / project ID (vault-relative) |
| **Claim ref** | Claim identity (Core claim identity rules apply) |
| **Source ref** | Layer A evidence path or source lineage ID |
| **Outcome** | `pass` \| `fail` \| `error` \| `skip` |
| **Evidence class** | `fixture` \| `bounded` \| `live-read` \| `pilot` (pilot never auto) |

---

## 3. Proposed suite sketch (non-normative YAML)

```yaml
# SKETCH ONLY — not a production schema; do not load from runtime.
schema_version: 1
suite_id: kci-engine-smoke
package_intent: AS-2.2-KCI-001
compat_pin_required: true
fixture_mode: true
truth_boundary: "KCI UNIT PASS ≠ CLAIM CERTIFIED"
authority:
  level: derived
  promote: false
units:
  - unit_id: claim-presence-001
    kind: claim.presence
    subject_ref: proj.demo.capability.auth
    expect:
      min_claims: 1
      lifecycle_in: [active, verified]
    on_missing: fail

  - unit_id: conflict-visible-001
    kind: conflict.presence
    subject_ref: proj.demo.capability.auth
    expect:
      unresolved_visible: true
      silent_winner: false
    on_missing: fail

  - unit_id: provenance-complete-001
    kind: provenance.complete
    source_ref: sources/demo/readme.md
    expect:
      hash_present: true
      lineage_present: true
    on_missing: error
```

---

## 4. Assertion kinds (draft catalog)

| Kind | Asserts | Forbidden side effects |
|---|---|---|
| `claim.presence` | ≥N claims for subject with allowed lifecycle | no claim create |
| `claim.absence` | 0 claims matching filter | no delete |
| `claim.text_digest` | SHA-256 of canonical claim text equals expect | no rewrite |
| `conflict.presence` | Unresolved conflict visible for subject | no auto-resolve |
| `conflict.silent_winner_absent` | No silent winner selection | refuse promote |
| `provenance.complete` | Source has hash + lineage fields | no forge |
| `index.drift_absent` | Generated lexical index matches rebuild digest | no mutate index |
| `protected_region.intact` | Human markers byte-identical across regenerate | abort on imbalance |
| `secret.findings_quarantined` | Secret metadata forces quarantine lane | never log secret body |
| `temporal.window_holds` | Claim validity window contains evaluation instant* | *fixture clock only |
| `query.deterministic` | Same query bytes → same result digest | no wall clock |

\* Evaluation instant must be suite-supplied fixture clock — never host now.

---

## 5. Outcome semantics

| Outcome | When |
|---|---|
| `pass` | Expectation matched; evidence class recorded |
| `fail` | Expectation mismatched; vault unchanged |
| `error` | Suite/ref/schema/path invalid; fail-closed |
| `skip` | Explicit `when` predicate false (documented only) |

Rules:

1. `error` fails the suite hard (non-zero future exit).
2. Any unit with `expect.silent_winner: false` that observes a silent winner →
   `fail` (and future engine must refuse promote paths).
3. Suite report always carries `authority_promoted: false`.
4. `pass` never upgrades evidence class to `pilot`.

---

## 6. Language keywords (reserved)

| Keyword | Role |
|---|---|
| `suite_id` / `unit_id` | `^[a-z][a-z0-9-]{0,63}$` |
| `kind` | From assertion catalog |
| `expect` | Pure data; no code eval |
| `on_missing` | `fail` \| `error` \| `skip` |
| `when` | Optional predicate over fixture facts only |
| `fixture_mode` | Default `true` pre-unlock |
| `promote` | Must be absent or `false`; `true` → refuse |

**No** embedded scripts, **no** Jinja, **no** model prompts as oracles.

---

## 7. Mapping to software-test vocabulary

| Software test | Knowledge unit analogue |
|---|---|
| `assertEqual` | `claim.text_digest` / query digest |
| `assertTrue` / presence | `claim.presence`, `provenance.complete` |
| `assertRaises` | Negative fixtures (see FIXTURE-PLAN) |
| Fixture setup | Synthetic vault under `docs/atlas-2.2/fixtures/` |
| Test runner | Future KCI engine (blocked until unlock) |
| Coverage report | Suite report `outcomes[]` |

---

## 8. Negative language (must remain expressible)

| Case | Expected outcome |
|---|---|
| Promote flag set on suite | `error` / refuse load |
| Ambiguous subject ref | `error` |
| Missing compat pin (post-unlock) | `error` |
| Secret body in unit file | reject at authoring / scan |
| Host absolute paths in refs | `error` |
| Wall-clock field in expect | `error` |

---

## 9. Non-claims

- This document does **not** authorize a parser or CLI.
- Example YAML above is **illustrative**; filenames reserved in FIXTURE-PLAN
  do not exist as payloads.
- Green future suites do **not** certify `v2.2.0` or authentic PILOT.

`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO`.
