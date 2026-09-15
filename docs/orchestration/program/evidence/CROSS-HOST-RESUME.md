# CROSS_HOST_READY = GO_SANITIZED_BRANCH_ONLY

Fresh-clone validated: `feat/prime-takeover-003-handoff-sanitized` =
`acf5a1f4c176b9a26dc4818c1878cae879cfb0b8` / tree `1a548a2069aefb1b324c2d8c9ac69b7221d74806`.

Do **not** clone contaminated `feat/prime-takeover-003-config-route` (`d539f88`).
Destructive cleanup of that ref still needs separate owner authorization.

`acf5a1f4c176b9a26dc4818c1878cae879cfb0b8` / tree `1a548a2069aefb1b324c2d8c9ac69b7221d74806`.

Destructive cleanup of that ref still needs separate owner authorization.

# CROSS-HOST-RESUME — Atlas Prime takeover-003 / t003f

**Status:** t003f is **TERMINAL** (`FAIL_NO_CANDIDATE`). **Do not resume t003f.**
**A1:** NOT_CLAIMED.

## Exact identities

| Item | Value |
|------|-------|
| HEAD | `ecc13dc830a629c7c6449f1aa3e156339a1809f0` |
| Workspace tree (at packaging) | `ed560297c19e37ca427f693accb36daf0439c9a8` |
| Program | `t003f` |
| Program SHA-256 | `d1029b12b1ca89f01355fcf03369f13b907f87abcecec0c76edd09f4b8444180` |
| Attempt 1 | `t003f.prime-a1.run.1.f68ee2a9` — COMPLETED_NO_A1_PATCH |
| Attempt 2 | `t003f.prime-a1.run.2.e0678593` — COMPLETED_NO_A1_PATCH |
| State (source-host only) | `/tmp/a002/t3f` — **not packaged**; see portable manifest |

## Counters (frozen)

- coding **2/2**
- reviewer **0/1 preserved** (never launched — no candidate)
- total launches **2/3**

## Freeze (permanent on this host)

- no resume of t003f
- no third coding attempt
- no reviewer launch against t003f
- no counter reuse
- no t003g on this host

## Evidence locations (in-repo portable package)

- `docs/orchestration/program/evidence/prime-takeover-003-t003f-terminal/`
- Final ledger SHA-256: `f2887bde008aa72bec22943055b5e5c667226bc941969b055bcfc5a2bfd999b4`
- Freeze ledger SHA-256: `190a487d13eb287276402844e27ec9471c6e6e540f21a9e977beaab1d93aac98`
- Portable state manifest SHA-256: `e629f738d5a68e8801c699340f16fa3fabf4ff5021e08716dd7b31d880ce902a`
- Machine record: `docs/orchestration/program/evidence/ATLAS-CROSS-HOST-RESUME-001.json`

Locks, PIDs, sockets, and runtime ownership under `/tmp/a002/t3f` and `/tmp/atlas-prime-e2e-002-ipc/t003f*` are **source-host-only**.

## Background notifications

Shell tasks `647852`, `647853`, and `647856` are **duplicates** of the same terminal t003f run. They create **no** new authorization or execution state.

## New-host entry gate

Do **not** create t003g immediately after cloning.

Prior micro-canaries (3/3) proved basic tool capability only; they did **not** predict production-task success.

On the new host, first run a **production-shaped disposable A1 canary** with:

1. comparable prompt size and context pressure
2. the same tool inventory and sandbox
3. multiple dependent read/edit/test operations
4. a scoped source modification
5. a new test
6. a native child artifact
7. structured terminal evidence
8. independent review

Require **at least two consecutive full passes**. A no-effect completion is **FAIL** even if the process exits normally.

If that canary fails with the same provider/model: mark the provider unsuitable for A1; do not spend another Prime root; escalate under a **separate** authorization.

## Required next-host capability work

1. Carry forward compaction reserveTokens sizing + wait_for_headless_completion remediation.
2. Keep role-separated budgets.
3. Pass production-shaped A1 canary 2/2 before any new Prime A1 root.
4. Never resume t003f.


## Security remediation (2026-09-15)

`CROSS_HOST_READY = NO_GO_PENDING_CLEANUP` until a fresh clone of the **sanitized**
branch reproduces expected commit/tree identities.

- Contaminated remote ref: `feat/prime-takeover-003-config-route` @ `d539f88` (tree `121487ca…`).
- Material: two `supervisorOwnerToken` values in attempt `prime-daemon.jsonl` evidence.
- Classification: source-host ephemeral task-local owner tokens; live registry match = no;
  daemon socket connect refused; local plaintext overwritten; stale socket removed.
- This sanitized branch replaces secret values with `[REDACTED SECRET]`.
- **Do not claim `d539f88` is sanitized** — history still contains the material.
- Destructive cleanup of the contaminated ref requires separate owner authorization
  (branch deletion and/or history rewrite). Do not force-push without that grant.
- New host must clone **`feat/prime-takeover-003-handoff-sanitized`**, not the contaminated branch.
