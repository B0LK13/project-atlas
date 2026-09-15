# PRIME-LOCAL-001 — Independent review of the gap-closure round (candidate 913bc791 + cc25b838)

Date: 2026-09-14 · Reviewer: independent verifier (fresh instance; no authorship of the changes under review)

## Candidate

- Repo: /home/gebruiker/atlas-prime-local-001, branch feat/prime-local-001
- Frozen head `913bc791637acc9afecb8a2429f5ba4e8f2dc709`, tree
  `f34a1684fc005ca2aed5ebecd03d29bc98cfe3d4` (verified via `git rev-parse`;
  clean verify worktree at /home/gebruiker/atlas-prime-verify-001 confirmed at
  the same head/tree)
- Docs-only top commit `cc25b838` touches only the acceptance matrix
  (`git diff --stat 913bc791..cc25b838` → 1 file, +23/-15)
- Range reviewed: `3f3ee03b^..cc25b838` — 6 commits, 14 files, +2531/-87
- Runtime: /home/gebruiker/prime-local-001-runtime at upstream pin
  `5d25a44bd22e1c1fe8321e141cd6c3932563d14c` (verified)

## VERDICT: PASS

No blocking findings. The closure round delivers exactly what the matrix
claims, the fail-closed properties hold in the code, every matrix row
cross-checked matches the code/tests, and the reviewer's own re-runs
reproduce the published numbers.

## Independence statement

The reviewer wrote none of the code under review. The full closure-round
diff was read; the P6 review was used as a format/claims reference only; the
matrix at `cc25b838`, the broker/adapter source at `913bc791`, the runtime
host patch, and the probe script were read directly. All test batteries,
ruff, mypy, the runtime vitest, and the sandbox probe were re-run by the
reviewer. No file was modified.

## Per-criterion findings

1. Credential/secret handling — OK. `_deny` journals only a sha256[:24]
   request digest; no prompts, keys, or tokens persisted. The TS client
   sends `prompt_sha256`, never the prompt. Socket, journal, and capture
   file live inside `evidence_dir`; nothing secret-bearing was added to the
   child env.
2. Fail-closed paths — OK. Denials are journaled (fsync) before reply;
   reserve rolls back slot/budget/fencing on journal OSError; the hook is
   inert without its env var; the TS client throws on close, timeout,
   malformed JSON, and oversize frames; empty/missing model and
   missing/malformed/negative depth are refused in both layers; fencing is
   enforced on commit and release.
3. Loops/retries/authority — OK. No unbounded loops or retries; slot
   semaphore denies immediately; dedup re-answers without double-spending;
   admission remains opt-in (`allow_children` gate) and native recursion
   stays disabled in shipped configs (repo-wide grep confirms no config
   enables it).
4. Fixture/real conflation — none found. No matrix row is graded above its
   evidence; PARTIAL/OPEN rows carry exact boundaries.
5. Sandbox — OK. The `--bind=<src>` attached-form fix covers
   `--bind=`/`--ro-bind=`/`--dev-bind=`, rejects empty sources, and keeps
   the writable-`/etc` rule; both forms are test-pinned. Probe re-run:
   `PRIME_SANDBOX_PROBE=PASS (4/4 denied)` with real positive controls.
6. Patch/runtime consistency — OK. Patch sha256
   `226405200865db6f677e846da420d2fa7c04e8b42d5bef8b77c1ffffb7416dba`
   matches the adapter constant and the runtime manifest; blob cross-check
   of both runtime files against the patch index lines is identical.
7. Old-evidence reusability — OK. The matrix pin registry states the
   coverage boundary exactly; no claim relies on old-program evidence
   without its pin.

## Reviewer's own re-runs (counts observed)

- 10 brief-listed files: **136 passed**; extended to all 18 Prime +
  orchestration-program files: **266 passed** (clean verify worktree)
- `ruff check .` → all checks passed; `mypy src` → no issues in 458 files
- Runtime admission regression → **5/5 passed** (faux provider)
- Sandbox probe → **4/4 denied**

## Non-blocking observations

1. `_validate_sandbox_argv` does not cover bwrap's `--bind-try` family
   (hardening debt, not a live hole; profiles are supervisor-approved).
2. Unparseable wire garbage is refused but not journaled (observability).
3. First-seen parent binding has a theoretical concurrent-first race;
   fail-closed afterward, unreachable in the adapter flow.
4. `allow_children=True` without a `child_admission` dict would hit a
   plain `assert` if `run()` were called without preflight; preflight
   always catches it first.
5. Terminal TS `release` failure propagates loudly; recoverable via broker
   dedup.
6. The dev worktree has uncommitted post-freeze work from a concurrent
   lane; per the pin registry it is outside this freeze and did not affect
   the review (all re-runs used the clean 913bc791 tree).

## Supervisor verdict acceptance

Exact verdict accepted into program evidence: **PASS, zero blockers**, on
frozen candidate `913bc791` (+ docs-only `cc25b838`). This acceptance covers
the gap-closure round only; it inherits nothing from the prior-program IV
(`b3273231`) and grants nothing new: real-provider execution, canonical
knowledge receipt, deployment canary/rollback, CI, and human IV remain open
exactly as the acceptance matrix records. No model-free COMPLETE is claimed.
