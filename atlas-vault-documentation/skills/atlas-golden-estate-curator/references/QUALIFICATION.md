# Qualification signals

Objective only. No trust scores.

| Signal | Golden | Challenge | Exclude |
|---|---|---|---|
| Clean git + README + no secrets | yes | | |
| Dirty worktree | | yes | |
| Missing README | | yes | |
| Stale docs | | yes | |
| Test/build failure signal | | yes | |
| Non-git folder | | yes | |
| Nested repo | | | yes |
| Secret-shaped file | | | yes |
| Malicious build script present | | | yes (never executed) |
| Duplicate identity | | | yes |

Monorepo is recorded as a signal, not auto-excluded.
