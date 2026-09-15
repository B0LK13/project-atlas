# D-080 Cloud IV

Independent (non-unit-test) Cloud IV against production freeze
`99aa937b3718cf0432bb688dbfa074daade7c049` /
tree `e73273f208009f9c317ffb489919e154938ee1c4`.

This IV used a **different** estate shape than the implementer unit tests
(120 flood clones + 4 late keepers + 1 mid-region keeper; 125 qualifying
projects; cap 10). Cloud did not access authentic `D:\`.

Attempted falsification:

| Claim | Attack | Verdict |
| --- | --- | --- |
| Candidate set is traversal-order independent | `name_asc` vs `name_desc` on the IV estate | PASS (identical path sets) |
| Noisy family cannot starve unrelated strong projects | 120 same-remote clones in `000-flood` vs late `999-keep` / `mmm-mid` | PASS (keepers preserved; ≤2 clones emitted) |
| Volume root is not a project | Simulated volume with `.git` + README | PASS (0 emitted) |
| No blank/dangling knowledge attachments | Root-level docs on that volume | PASS (0 / 0) |
| Cap honesty | 125 seen, cap 10 | PASS (`scan_complete=false`) |

```
CLOUD_IV = PASS
TRAVERSAL_ORDER_SEMANTIC_DRIFT = 0
AUTHORIZED_VOLUME_ROOT_FALSE_PROJECTS = 0
EMPTY_PROJECT_ID_ASSIGNMENTS = 0
DANGLING_PROJECT_RELATIONS = 0
NEW_HIGH = 0
NEW_SECURITY_HIGH = 0
```

Local D-081 must still prove the five authentic anchors on `D:\`.
