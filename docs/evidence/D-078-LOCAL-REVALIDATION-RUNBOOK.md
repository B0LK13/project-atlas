# Local D-078 revalidation runbook

Cloud cannot access authentic `D:\`. Local must prove policy first, then
rerun authentic estate Run A against the **volume root**, not invented
subdirectories.

D-075 optimized documentation remains Local's job. Do not expect Cloud to
have reconstructed the five external repositories.

## Exact target

```
HEAD = fcaf4f5e152b162a52bfc1c28654ff11acbeb842
TREE = 119c779f8995ab576a231aaa06a334fb813cd737
```

```bash
git fetch origin cursor/d049-authorized-volume-root-6f85
git checkout fcaf4f5e152b162a52bfc1c28654ff11acbeb842
test "$(git rev-parse HEAD^{tree})" = "119c779f8995ab576a231aaa06a334fb813cd737"
```

If HEAD/TREE differ → `VALIDATION_STALE`. Stop.

Do **not** revalidate an evidence-only tip above this freeze.

## Phase 1 — policy semantics (must all PASS before Run A)

1. Default refuse:

   ```
   atlas discover --root D:\
   ```

   Expected: non-zero exit, `FILESYSTEM_ROOT_NOT_ALLOWED`, `SCAN_STARTED = NO`.

2. Explicit owner-volume accept:

   ```
   atlas discover --root D:\ --root-mode owner-authorized-volume --json
   ```

   Expected: exit 0, `authorized_root_mode = OWNER_AUTHORIZED_VOLUME_ROOT`,
   `volume_root_authorized = true`,
   `volume_root_kind = NON_SYSTEM_WINDOWS_VOLUME`,
   scan starts and remains physically bounded to `D:\`.

3. System drive still refuses:

   ```
   atlas discover --root C:\ --root-mode owner-authorized-volume
   ```

   Expected: `SYSTEM_VOLUME_ROOT_NOT_ALLOWED`.

4. External reparse/junction escape from authorized `D:\` is **not followed**.
   `PATH_ESCAPES = 0`. `EXTERNAL_REPARSE_TARGETS_FOLLOWED = 0`.

Also confirm:

- home remains refused even with `--root-mode owner-authorized-volume`
- a non-root directory plus volume mode is refused
  (`VOLUME_MODE_REQUIRES_WINDOWS_VOLUME_ROOT`) — no silent reinterpret
- human CLI states this is not an ordinary bounded-directory scan
- API `/v1/discovery` and Web `/discovery` project the same mode fields
  (no UI reclassification)

## Phase 2 — authentic estate Run A

Only after Phase 1 PASS.

Authorized root is **exactly** `D:\`.

```
atlas discover --root D:\ --root-mode owner-authorized-volume --vault <vault>
```

Do **not** substitute:

- `D:\dev-ai`
- `D:\dev-web`
- five individual project roots
- any invented subdirectory aggregate

Reconstruct D-075 documentation locally before this run if those five
anchors must be readable.

This is a **new** authentic run against a **new** freeze. Do not edit the
historical `LOCAL_RUN_A @ 198350319 = FAIL` record into PASS.

## Out of scope

- D-042 Conversational Capture (`D_042_EXECUTION_GATE = CLOSED`)
- Documentation Health / Living Roadmap / Project Memory / Momentum /
  Portfolio / 2.3 / OPT / AutoLab / Prime
- Rewriting Run A history
- Merging #351 before Local PASS
