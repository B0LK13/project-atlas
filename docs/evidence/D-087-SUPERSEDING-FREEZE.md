# D-087 superseding performance freeze

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-D087-PATH-INDEX-PERFORMANCE`
PACKAGE: `AS-CODER-ALPHA-D049-AUTHORIZED-VOLUME-ROOT-001` (same production lane as D-078 / D-080 / D-084)
PR: `#351` (do not merge)

## Lineage

```
CURRENT_MAIN = 198350319c17b4de0665f972fda0bc51420cd686
D084_PRODUCTION_FREEZE = 2fcf8186d4a2c6d4209cee82b6d6f076e2119589
D084_TREE = 4148e9a63de0089736bea1c0b2631dd1e4fe72e5
D085_AUTHENTIC_ESTATE_RUN_A = PARTIAL
D085_CORRECTNESS = PASS
D085_PERFORMANCE = SEVERE
```

D-084 remains the historical correctness-success / performance-PARTIAL
candidate. D-087 is the superseding first-scan performance candidate.
D-078 root policy, D-080 container / knowledge-relation truth, D-083
Windows CI portability, and D-084 hierarchical-fair selection remain PASS
and must not regress.

## Production freeze (Local D-088 target)

```
D087_HEAD = b2b5d9b9fc7e4d3aff69fea3e1a90d9c950b0b78
D087_TREE = 14318297c5fbf40b4fff054ad27126ee4c89db7f
PRODUCTION_SEMANTIC_CHANGES_AFTER_D087_FREEZE = 0
CANDIDATE_SELECTION_POLICY = deterministic_hierarchical_fair_v2
```

Later evidence-only commits on this branch are not the Local IV target.

## D-085 authentic result (preserved)

```
D085_AUTHENTIC_ESTATE_RUN_A = PARTIAL
KNOWN_EXPECTED_FOUND = 5/5
OWNER_ANCHORS_STARVED_BY_CAP = 0
NOISY_SUBTREE_MONOPOLY = NO
AUTHORIZED_VOLUME_ROOT_EMITTED_AS_PROJECT = 0
DIRS_VISITED = 301752
ELAPSED = 01:22:01
PROJECT_CANDIDATES_SEEN = 11485
PROJECT_CANDIDATES_PRESELECTED = 1500
PROJECT_CANDIDATES_ENRICHED = 1500
PROJECT_CANDIDATES_EMITTED = 500
KNOWLEDGE_CANDIDATES_SEEN ≈ 24604
D084_PERFORMANCE_RESIDUAL = SEVERE
```

## Profile (Cloud synthetic, not authentic D:\)

Hypothesis A was instrumented, then confirmed:

```
HYPOTHESIS_A = KNOWLEDGE_PROJECT_ANCESTRY_O_KxP_WITH_REPEATED_RESOLVE
HYPOTHESIS_A_KNOWLEDGE_ANCESTRY = CONFIRMED
```

Independent Cloud IV estate (`iv-zone-*`, different from unit tests):

```
DOMINANT_PHASE = filesystem_traversal
DOMINANT_PHASE_PERCENT = 60.70
UNDER_AUTHORIZED_CALLS = 1
PATH_RESOLVE_CALLS = 2790
KNOWLEDGE_PROJECT_ANCESTRY_CHECKS = 8580
K_TIMES_P = 901500
PATH_RESOLVE_CALLS_DURING_IN_MEMORY_SELECTION = 0
```

D-084-style linear ancestry on the same selected set (K=1001, P=500):

```
PATH_RESOLVE_CALLS_BEFORE = 775804
PATH_RESOLVE_CALLS_AFTER = 0
KNOWLEDGE_PROJECT_ANCESTRY_CHECKS_BEFORE = 387426
KNOWLEDGE_PROJECT_ANCESTRY_CHECKS_AFTER = 2901
TOTAL_TIME_BEFORE (ancestry loop only) = 19.630935s
TOTAL_TIME_AFTER (ancestry loop only) = 0.002442s
CLOUD_BENCH_SPEEDUP = 8039.7
LINEAR_VS_INDEX_HIT_DRIFT = 0
```

Full synthetic discovery after the index (not authentic D:\):

```
TOTAL_TIME_AFTER = 0.705404s
TRAVERSAL_TIME = 0.427378s
KNOWLEDGE_SELECTION_TIME = 0.003188s
PROJECT_ENRICHMENT_TIME = 0.085587s
```

Traversal is now the dominant remaining phase. That is intrinsic
first-scan directory walk, not O(K*P) resolving. D087-C scandir reuse
and D087-D cache-recording optimization were therefore NOT_NEEDED.

```
IN_MEMORY_PATH_INDEX = IMPLEMENTED
RESOLVED_PATH_REUSE = IMPLEMENTED
SCANDIR_METADATA_REUSE = NOT_NEEDED
CACHE_RECORDING_OPTIMIZATION = NOT_NEEDED
STALE_CACHE_TRUTH = 0
```

## What D-087 changed

- Component-aware in-memory ancestor walk for knowledge→project matching
  (`O(K * depth)` / `O(K log P)` class, not `O(K * P * Path.resolve)`).
- Already-resolved canonical keys reused after the traversal safety
  boundary. Untrusted paths still go through `_under_authorized`.
- Bounded, non-authoritative operation counters on `scan.operation_counters`.
  Phase timings live in `_perf` and are stripped from written reports.
- Forbidden naive prefix matching (`d:/foo` is not an ancestor of
  `d:/foobar`).

Not done (intentionally):

- candidate-selection redesign
- incremental / second-scan discovery
- scandir metadata reuse
- stale-cache authority
- D-042 implementation
- merge of #351

## Cloud IV falsification

```
PROJECT_SELECTION_SEMANTIC_DRIFT = 0
KNOWLEDGE_RELATION_SEMANTIC_DRIFT = 0
D078_POLICY_PRESERVED = YES
BOUNDED_ENRICHMENT_PRESERVED = YES
NAIVE_PREFIX_BUG = NO
FOOBAR_FALSE_ASSIGN = NO
PATH_ESCAPES = 0
SYMLINK_ESCAPES_DETECTED = 1
BLANK_PROJECT_RELATIONS = 0
CLOUD_IV = PASS
```

## Merge rule

```
MERGE_RECOMMENDATION = BLOCKED_PENDING_LOCAL_D088
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PARTIAL
D_049_FINAL_ACCEPTANCE = PARTIAL
D_042_EXECUTION_GATE = CLOSED
```

## Next action

`LOCAL VALIDATE EXACT D087 FREEZE AGAINST AUTHENTIC D:\.`
