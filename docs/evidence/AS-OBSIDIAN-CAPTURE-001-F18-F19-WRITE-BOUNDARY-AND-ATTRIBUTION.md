# AS-OBSIDIAN-CAPTURE-001 F18/F19 — write boundary and write attribution

Status: **EVIDENCE RECORD — NOT A CLOSURE CLAIM**

Two questions, deliberately kept apart because they have different answers and
different limits:

| | question | package |
|---|---|---|
| F18 | *did a write alter operator-owned bytes?* | runtime write boundary |
| F19 | *which execution did it, under what authority, against which state?* | attribution |

F18 shipped first and is useful without F19. F19 does not replace it.

---

## F18 — the write boundary

`tests/unit/human_content_boundary.py` intercepts the OS primitives note bytes
reach disk through: `os.replace`, `os.rename`, `os.open`, `os.close`,
`os.fdopen`, `builtins.open`, `Path.write_bytes`, `Path.write_text`. When the
destination already contains `<!-- BEGIN HUMAN:` and the incoming bytes carry
different human regions, the write is recorded as a violation.

Interception sits at the primitive rather than at Atlas's own helpers, so it is
**spelling-independent**: a writer does not have to call the blessed helper to
be seen.

### Measured: 12 bypass routes, all caught

`BYPASS_ROUTES` in `test_as_obsidian_capture_001_f18_write_boundary.py`
enumerates twelve ways to damage a protected note while avoiding the reviewed
writers — hand-rolled `write_text`/`write_bytes`, a private `tmp` +
`os.replace`, the same via `os.rename`, `capture_io.write_atomic_under_root`,
dynamic import then clobber, `functools.partial`, `os.fdopen`, a raw fd via
`os.write`, `shutil.copyfile`, `shutil.move`, and `builtins.open`. All twelve
are detected.

### Measured: the boundary itself can fail

`test_f18_the_boundary_itself_can_fail` unhooks each intercepted primitive in
turn and asserts the corresponding route then escapes. Without it, "all routes
caught" would be equally consistent with a detector that reports success
unconditionally.

### What Windows CI found that POSIX could not

Three defects, all mine, none reproducible on Linux:

1. **The fixture was the source of the difference.** `_note` seeded notes with
   `Path.write_text`, which translates `\n` to `\r\n` on Windows. The prior
   note was then CRLF while the payload was LF, so a *correct* write looked
   like damage. Seeding is now byte-exact.
2. **`os.rename` onto an existing file raises `WinError 183` on Windows** where
   it overwrites on POSIX. That route cannot damage a protected note there at
   all, so it is not an escape -- it is inapplicable. The runner now records
   inapplicable routes by name and asserts that at most two of the twelve may
   be skipped, so "no route escaped" cannot become true by everything being
   skipped.
3. **The boundary itself had a real gap.** Fixing (1) exposed it: the
   `Path.write_text` hook checked the *payload it was handed*, not the bytes
   that landed. Text mode is not byte-transparent, so a write that translates
   line endings rewrites operator bytes while every word still matches -- and
   the hook could not see it. `Path.write_text` is now verified **after** the
   bytes land (`_check_landed`), which cannot be fooled by anything the write
   layer does on the way down. `builtins.open` already checked at descriptor
   close and was measured to catch it unaided.

Defect (3) is the same class as the CRLF-translating *read* that
`protected_regions.read_note_text` exists to prevent, arriving from the write
side. It is now pinned by a test that probes whether text mode actually
translates rather than assuming it from the platform name, so it stays honest
if a future Python changes the default, and skips with the platform named where
there is nothing to detect.

These were verified locally by simulating both Windows behaviours (a
non-overwriting `os.rename` and newline-translating text mode) on Linux: 8
passed under simulation, 24 passed + 1 skipped natively.

### Stated limitation: detection is not attribution

`Violation.origin` records the innermost stack frame inside
`src/project_atlas`. That was originally read as "the responsible writer" and
**that reading was wrong**: a caller that hands damaged bytes to
`capture_io.write_atomic_under_root` and a caller that writes them directly are
the same act with different plumbing. The property is now named
`landed_via_atlas_helper` and carries the comment *this is plumbing, not
responsibility, and must never be used as a gate*. The limitation is pinned by
`test_f18_the_boundary_detects_damage_but_cannot_attribute_it`.

That limitation is what F19 addresses.

### Report-only, and why

`tests/conftest.py` installs the boundary **only** under
`--human-content-boundary`. Enabling it for every session was measured and
withdrawn: it broke three tests that spawn a nested `pytest`
(`test_codex_sec_001_002_provenance.py::test_sec002_toctou_...`, and two
`test_security_regression_seed.py` parametrisations), because the child process
loads the same conftest and the added option changed its exit status. The
sensor is not at fault and its census is real, but **a monitor that changes the
result of the suite it observes is not an observer**. Making it continuous
requires that nested-pytest interaction to be fixed first, which belongs to the
owners of those tests and is recorded rather than worked around.

Census from one opt-in full-suite run, reported and not gated:
`573 protected write(s) checked, 87 altered operator regions`. **That run was
not fully green** -- it ended `1 failed, 5789 passed`, the failure being the
nested-pytest test described above, which is precisely why the boundary is
opt-in. The census figure comes from a run with a known failure and is reported
with that caveat rather than as a clean measurement. Those 82 are
**not** 82 defects — most are fixtures that legitimately rewrite their own
notes. Presenting the raw count as a defect count would be exactly the
overclaim this record exists to avoid.

---

## F19 — attribution

### It reuses Atlas's existing authority record

No new identity system was introduced. `AgentLease`
(`src/project_atlas/orchestration/autonomy/models.py`) already carries every
field the question needs:

| the question | the existing field |
|---|---|
| which execution | `agent_id`, `lease_id` |
| under what authority | `capabilities`, `authorized_paths`, `forbidden_paths`, `active` |
| against which exact state | `base_pin` (40-char git SHA) |

The lease record was already well formed. What did not exist was any
**connection** between it and a write. That connection — and only that — is
what F19 adds.

### The binding primitive

A `ContextVar`. It follows the execution rather than the call site, so it
survives helpers, wrappers, aliases and `await`. It does not cross a process
boundary, which is correct rather than unfortunate: a child process carries no
trusted identity, so attributing across it would launder an unknown into a
known.

Trust comes from a **minted token**, not from the presence of a lease object. A
binding constructed by hand carries a token this module never minted and is
refused. A token is destroyed when its `bind()` block exits, so a binding
captured inside the block and replayed afterwards stops passing — which is how
lease *loss* becomes observable rather than silent.

### The classification vocabulary, used without widening

| state | meaning | producer |
|---|---|---|
| `GOVERNED_AND_ATTRIBUTED` | trusted lease active, path in scope | in-process classify |
| `ATTRIBUTED_BUT_UNAUTHORIZED` | trusted lease active, path out of scope | in-process classify |
| `DETECTED_BUT_UNATTRIBUTED` | write seen, no trusted lease (incl. a *refused* claim) | in-process classify |
| `OUTSIDE_OBSERVABLE_BOUNDARY` | regions changed with no observation to explain it | `reconcile()` only |
| `UNKNOWN` | observation was not installed, so absence proves nothing | classify / `reconcile()` |

`test_f19_every_state_in_the_vocabulary_is_actually_emitted` produces each
state from a real call. An earlier revision asserted a hand-written set against
the enum, which is the exact shape of a test that cannot fail for the reason it
claims — the literal would have been updated alongside any new member and
stayed green while nothing emitted it.

### Measured: the adversarial suite

Seventeen tests, of which one is the happy path. The rest attack the binding:
forge it, refuse-control the forgery, replay it after expiry, bind an inactive
lease, write outside scope, overlap authorized with forbidden, use an empty
allow-list, nest two leases, and cross a thread and an `asyncio` task boundary.

Inheritance is **measured, not assumed**: an `await`ed task is the same
execution and stays `GOVERNED_AND_ATTRIBUTED`; a bare `threading.Thread` starts
with an empty context and is reported `DETECTED_BUT_UNATTRIBUTED`. The
asymmetry is a CPython property and is pinned so a refactor cannot change it
silently.

### Measured: seven mutations, each turning the suite red

The classifier's protections are load-bearing. Each mutation was applied to the
module, the suite run, and the module restored (`git diff` empty afterwards):

| mutation | result |
|---|---|
| trust any claimed binding (drop the mint check) | 2 failed, 12 passed |
| authorize everything (`_authorized` → `True`) | 4 failed, 10 passed |
| ignore `forbidden_paths` | 1 failed, 13 passed |
| ignore `active=False` | 1 failed, 13 passed |
| treat silence as clean (drop the `installed` check) | 2 failed, 12 passed |
| let `reconcile` claim observation it did not have | 1 failed, 13 passed |
| never destroy the token on `bind()` exit | 1 failed, 13 passed |
| *(baseline and restored)* | **14 passed** |

### End to end, through a real writer

`obsidian_projection._write_atomic` damaging a protected note reports:

- inside lease scope → `GOVERNED_AND_ATTRIBUTED`, carrying `agent_id`,
  `package_id` and `base_pin`;
- identical damage, lease scoped elsewhere → `ATTRIBUTED_BUT_UNAUTHORIZED`,
  actor still named;
- no lease bound → `DETECTED_BUT_UNATTRIBUTED`, and **no actor is invented**.

### Stated limitation: not a defence against hostile in-process code

Anything sharing this interpreter can add to `_MINTED`, exactly as it can
unhook the boundary observing it. Nothing inside a process defends against
arbitrary code inside that same process. This is pinned by
`test_f19_the_binding_is_not_a_defence_against_hostile_in_process_code`, which
**passes when the attack succeeds** — it documents the threat model rather than
pretending the defence extends further than it does.

The mechanism is trustworthy against accident, refactoring and ordinary
mistakes. It is not a security boundary.

---

### The measured answer to the attribution question

Full-suite census with the boundary and ledger installed:

```
attribution: GOVERNED_AND_ATTRIBUTED=1, ATTRIBUTED_BUT_UNAUTHORIZED=1,
             DETECTED_BUT_UNATTRIBUTED=565
  2/567 protected writes carry a trusted execution identity (0%)
```

The two attributed writes are F19's own tests binding a lease deliberately.
**Atlas can currently explain none of its real protected writes.** That is the
honest state of the system, and it is the number this package exists to make
visible rather than to improve by itself.

### Stated limitation: demonstrated, not deployed

Nothing in `src/project_atlas` calls `bind()`. F19 proves the binding works and
that its protections are load-bearing; it does **not** make Atlas attribute its
own writes today.

The integration point is identified rather than left vague.
`leases.py:grant_lease` is, per its own callers' comments, *the sole place an
`AgentLease` is ever created*, and it is reached in production from
`governor.py:596`. A single `bind()` around the work a granted lease authorizes
would therefore cover every governed execution -- one call site, not a
sprinkling.

That change is a `src/` change this lane has not made and has not been
authorized to make. It is written down here as a precise handoff so the next
owner inherits a location and a rationale rather than a research task.

## What this does NOT claim

- **Not** `A_WRITER_CANNOT_SILENTLY_BYPASS_HUMAN_CONTENT_INTEGRITY`. The
  boundary is report-only in-process and absent out-of-process.
- **Not** cross-process attribution. The process boundary carries no trusted
  identity, so a subprocess write is `OUTSIDE_OBSERVABLE_BOUNDARY` and must
  stay there until that changes.
- **Not** a production runtime control. Both modules live under `tests/`;
  nothing in `src/project_atlas` imports them and no shipped code path is
  altered.
- **Not** a closure of #759. The frozen ingestion surface is untouched and
  remains owner-gated.
- **Not** an owner grant. `MERGE_AUTHORIZATION = NOT_GRANTED`; this record is
  evidence for review, not a decision.
