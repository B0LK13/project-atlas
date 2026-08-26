# D-037 — Canonical Golden Estate Path Reconciliation

```text
D037_STATE = COMPLETE
CASE = A
D036_GLOBAL_FRONTIER_VALID = NO
MERGE_AUTHORIZATION = NOT_GRANTED
```

## 0. Exact Object Binding (40-char SHAs)

| Object | HEAD | TREE |
|---|---|---|
| **MAIN** | `f6b2495a03196901a5a72c2cf3451d4504b54d5f` | `9c670d710ec63d36fea70c6a181c088b79294336` |
| **PR607** | `80dd9d01a38ee3720b759cfd51e9262ce3235ea2` | `0eab2f88b92830b8a2bac917633abff2e29047a1` |
| **PR608** | `94786c9c6e59aa0934296a71e8190959e34e914e` | `a26b9caa95ae37d39d20f489683174ce166e903a` |
| **PR609** | `4fe172ffc14713db9cfe4d698848b770d69a0fe6` | `b53de8667e48e625d0fdcea540a52f6b42f28b22` |
| **CERT609 production** | `dc75651a28f10b7f07ea6da0c446919e36d64b99` | `0aabded5cbbd45567a0d4b338d94d0096af73442` |

```text
D036_PR608_TREE_BINDING_VALID = NO
PR608_EXACT_TREE = a26b9caa95ae37d39d20f489683174ce166e903a
```

(D-036 truncated `a26b9caa93a` / `a26b9caa95ae3` — recomputed from Git.)

## 1. Canonical Path Decision — CASE A

**CANONICAL_CARRIER = PR609**

| Criterion | PR608 stack (#607→#608) | PR609 |
|---|---|---|
| GE skill files | 19 | 19 |
| GE byte identity vs other | identical | identical |
| CI GE test path | YES | YES (byte-identical `ci.yml`) |
| Lane C WORKLOG restoration | YES (via #607) | YES (native KEEP_BOTH) |
| Certification depth | Windows GE only | GE+Atlas3+RR+IV (540/161/48) |
| Integration hops | 2 (607 then 608) | 1 (direct from main) |

```text
GE_BYTE_EQUIVALENCE = PASS (19/19 identical blobs)
GE_SEMANTIC_EQUIVALENCE = PASS
PR608_REQUIRED_UNIQUE_DELTA = 0
PR609_REQUIRED_UNIQUE_DELTA = 0
ACTIVE_GE_INTEGRATION_PATHS = 1
CANONICAL_GE_CARRIER_AMBIGUITY = 0
```

### Dispositions

| PR | Disposition |
|---|---|
| **#609** | `CANONICAL_OWNER_GATE` |
| **#608** | `SUPERSEDED_BY_PR609` |
| **#607** | `REQUIRED_SEPARATE_GOVERNANCE` (docs/provenance; not prerequisite for #609) |

```text
PR607_REQUIRED_BEFORE_CANONICAL_MERGE = NO
NEXT_OWNER_ACTION = AUTHORIZE_MERGE_PR_609
```

## 2. Path Decomposition

**D609 vs MAIN** — GE skill (19 files), CI additive GE tests, WORKLOG KEEP_BOTH, evidence/tooling.

**D608 effective vs MAIN** — #607 governance docs + same GE/CI as #609.

**608-only vs 609** (non-GE): governance evidence from #607 stack (`D-028-INTEGRATED-ATLAS3-STACK`, `D-029-SUPERSESSION-CLEANUP`, D-034/D-035 packets). Not required for GE integration.

**609-only vs 608**: D-028 carrier evidence + seal harness scripts.

## 3. WORKLOG / Encoding

| Check | #607 | #608 | #609 | MAIN |
|---|---|---|---|---|
| Lane C REPORT READ | YES | YES | YES | NO |
| GE chronology | YES | YES | YES | partial |
| Mojibake (UTF-8 corruption) | YES | YES | YES | YES |

Mojibake is **pre-existing on main** (D-025 `-X theirs` Atlas3 WORKLOG entries). Not introduced by carrier ambiguity.

```text
WORKLOG_ENCODING_CORRUPTION = YES (pre-existing)
WORKLOG_HISTORICAL_UNEXPECTED_MUTATIONS = YES (pre-existing)
AUTONOMOUS_REMEDIATION_REQUIRED = NO (BACKLOG_OPTIONAL post-merge docs fix)
```

## 4. CI Comparison

```text
CI_TRIGGER_CHANGE = NO
CI_PERMISSION_CHANGE = NO
CI_JOB_REMOVAL = NO
CI_EXISTING_TEST_REMOVAL = NO
CI_GATE_WEAKENING = NO
CI_GE_TEST_ADDITION = YES (#608 and #609; identical ci.yml)
CI_CODE_FAILURE = NO
CI_EXECUTION_NODE = BLOCKED_EXTERNAL (budget; jobs fail ~3s pre-step)
CI_POLICY_NODE = BLOCKED_BY_OWNER
```

## 5. Windows Canonicalization

```text
CANONICAL_WINDOWS_PACKET = D-037-WINDOWS-EXECUTION-PACKET.json
CANONICAL_WINDOWS_HEAD = 4fe172ffc14713db9cfe4d698848b770d69a0fe6
CANONICAL_WINDOWS_TREE = b53de8667e48e625d0fdcea540a52f6b42f28b22
ACTIVE_WINDOWS_TARGETS = 1
```

Superseded (do not execute): D-029 Windows packet if bound to #608 draft path.

## 6. PR542

```text
PR542_DISPOSITION = BACKLOG_OPTIONAL
```

Windows lost-race ingest fix; not a current GE/Atlas3 certification invariant.

## 7. Supersession

```text
SUPERSESSION_SET_SIZE_PRE = 44
SUPERSESSION_SET_SIZE_POST = 45 (+PR608 carrier)
SUPERSESSION_DRIFT = 0
NEWLY_SUPERSEDED_CARRIERS = PR608
```

## 8. Frontier Invariant

```text
READY = 0
DERIVABLE = 0
UNKNOWN_REQUIRES_AUDIT = 0
AUTONOMOUS_REMEDIATIONS = 0
AUTONOMOUS_NODES_REMAINING = 0
GENUINE_OWNER_ONLY_FRONTIER = YES
```

Machine evidence: `D-AUG26-CANONICAL-GE-PATH-RECONCILIATION-037.json`

Bound: 2026-08-26.
