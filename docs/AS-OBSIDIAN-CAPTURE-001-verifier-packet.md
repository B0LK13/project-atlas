# AS-OBSIDIAN-CAPTURE-001 — independent verification packet

For a fresh agent in a fresh worktree. Nothing below is self-certified: each
target is an attack to attempt, not a result to confirm.

## Candidate

| Field | Value |
| --- | --- |
| Branch | `feat/as-obs-001-conversational-knowledge-capture` |
| Base | `origin/main` @ `31e07770992723e340f82e7e79c8483da17fa32e` (tree `b32950090463e7186896c0791bf3a840a673cf4b`) |
| Head | `bac590cf` (tree `c4f6ebe2`) |
| Commits | `1e41a97c` feature · `610821f8` schema · `aec7d6e8` Atlas-3 guard · `715b5f2f` docs · `816d937e` IV packet · `8c39e0d8` Windows atomic-write · `729acb65` IV rebase · `d4bd4a8b` **R1 projection anchor** · `bac590cf` **canonical path validation** |
| Superseded | `816d937e` (Windows), `729acb65` (**IV FAIL** — default projection root escape) |

`git log --oneline 31e07770..HEAD` should show exactly those ten. **Do not reuse
evidence from `729acb65` or earlier**: those heads are historical only, and
`729acb65` failed independent verification on the finding re-attacked in V7.

## Environment (do not skip)

The repository root `.venv` resolves to **whichever checkout owns it**. A
verification worktree must build its own, or it will silently exercise another
lane's source:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -c "import project_atlas; print(project_atlas.__file__)"   # must be THIS worktree
```

## Changed surface

```text
src/project_atlas/capture_io.py               new   contained atomic write (shared by both writers)
src/project_atlas/capture_sources.py          new   source adapters + CaptureRequest
src/project_atlas/obsidian_capture.py         new   capture service / raw store / dedupe / routing
src/project_atlas/obsidian_capture_note.py    new   Obsidian output adapter
src/project_atlas/schemas/raw-capture.schema.json  new
src/project_atlas/schema.py                   +2    registry entry
src/project_atlas/config.py                   +68   [tool.atlas.capture] / [tool.atlas.obsidian]
src/project_atlas/cli.py                      +301  capture text|raw-list|retry|show
tests/unit/test_as_obsidian_capture_001.py    new   65 tests
tests/integration/test_as_obsidian_capture_001_journey.py  new  12 tests
tests/unit/test_atlas3_demo_isolation_001.py  mod   guard remediation + G-matrix
tests/unit/test_schema.py                     +1    raw-capture registry entry
```

Nothing on the demo-isolation `DENY` list is touched. `_OWNER_APPROVED_EXCEPTIONS`
is unchanged.

## Commands

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src
.venv/bin/python -m pytest
.venv/bin/python -m pytest tests/unit/test_as_obsidian_capture_001.py \
    tests/integration/test_as_obsidian_capture_001_journey.py \
    tests/unit/test_atlas3_demo_isolation_001.py -q
```

CLI smoke (needs a vault; `atlas init --output <dir>` then a project dir):

```bash
echo "text" | atlas capture text --vault <v> --stdin
atlas capture text --vault <v> --clipboard --source-type conversation --application chatgpt
atlas capture text --vault <v> --project <id> --text "..."
atlas capture raw-list --vault <v> --json
atlas capture show  --vault <v> --capture-id rcap-...
atlas capture retry --vault <v> --capture-id rcap-...
```

## Verification targets — try to break these

### V1 — Raw evidence representation drift (INV-001)

Capture payloads with `LF`, `CRLF`, lone `CR`, mixed endings, no trailing
newline, trailing whitespace, a UTF-8 BOM, NFC/NFD pairs, and lone surrogates.
Compare `rcap-*.txt` **bytes** against the input bytes, not the decoded string.
Then `atlas capture retry` and confirm the content hash does not move.

Attack the split deliberately: identity canonicalization normalizes line
endings and applies NFC, but the *stored* bytes must not. A previous defect
here was `Path.read_text` applying universal-newline translation on readback.

### V2 — Path containment (§32, §64)

Include the case that only appeared after the Windows fix: symlink the
**capture store's own parent** (`generated/ops/raw-captures`) out of the vault
and confirm the capture fails closed with `PATH_ESCAPES_VAULT` and zero bytes
written outside.

Push absolute (`/etc`), traversal (`../../etc`), drive-relative (`C:evil`),
UNC (`\\server\share`), Windows-reserved (`con`, `nul`), and trailing dot/space
values through `[tool.atlas.obsidian] routing.*`, `--project`, `--title`, and
`--obsidian-vault`. Symlink a routing directory to a location outside the
configured root and confirm nothing lands there. Confirm that a rejected
routing value writes **nothing at all**, including no raw evidence.

### V3 — Redaction leakage (§38, NFR-004)

Put each secret pattern from `project_atlas.secrets` on the **first line** of a
capture — that is what feeds the title heuristic, which feeds the note filename
on disk. Then grep for the literal secret in: the note body, the note
frontmatter, the note *filename*, the capture record JSON, `latest.json`, and
stderr logs. It must appear in exactly one place: `rcap-*.txt`.

### V4 — Concurrent dedupe and the atomic-write layer (§49)

Fire N simultaneous identical captures at one vault. Expect exactly one
`rcap-*.json`, one `rcap-*.txt`, one note, zero leftover `*.tmp`, and no
raised exception.

Honest contract boundary — do not over-read the result:

```text
PERSISTENCE_IDEMPOTENCY                        = contracted
SEQUENTIAL_DUPLICATE_SIGNAL                    = contracted (2nd sequential capture -> duplicate: true)
CONCURRENT_DUPLICATE_SIGNAL_LINEARIZABILITY    = NOT contracted
```

Under a genuine race several callers may each return `duplicate: false` while
converging on one artifact set. The contract is *no uncontrolled duplicate
output*, not *exactly one non-duplicate result*.

**Windows specifically.** The Windows leg is where this layer failed before
(CI run `33956239428` on the superseded head `816d937e`: 4 ×
`unsafe capture store escapes root` + 2 × `PermissionError(13)`). Re-attack it:

- A containment check must never be satisfied by retrying. Confirm the
  authoritative `ensure_under_root` in `capture_io.write_atomic_under_root`
  runs against an **existing** directory and is not wrapped in a retry loop;
  the retries cover only `os.replace` and `mkdir`.
- Confirm the lexical gate precedes any `mkdir`, so a rejected target is never
  materialized.
- Confirm the retry is bounded and re-raises (monkeypatch `os.replace` to fail
  permanently) rather than looping.
- Confirm a temp file never survives either success or failure.
### V7 — Default projection trust anchor (the R1 finding — attack this first)

`729acb65` wrote the derived note **outside** the Atlas vault and still
reported `status: ok` when a symlink was pre-planted at either

```text
<vault>/generated/obsidian/captures -> /outside      (leaf)
<vault>/generated/obsidian          -> /outside      (intermediate)
```

The claim now is that the *implicit* projection is anchored on the **Atlas
vault**, not on itself, while the *explicit* external opt-in keeps its own
anchor. Re-establish that independently:

| attack | required |
| --- | --- |
| leaf link | `partial` + `PATH_ESCAPES_VAULT`, 0 bytes outside |
| intermediate link | same |
| `generated -> outside` | same |
| relative link target | same |
| symlink chain (link → link → outside) | same |
| link planted *after* the first capture, before a `retry` | same |
| normal default root | `ok`, note under `<vault>/generated/obsidian/captures` |
| explicit `--obsidian-vault` | `ok` — must **not** have become a failure |

Also check the ordering claim, not just the outcome: with an intermediate
link planted, assert **nothing at all** is created on the far side — not even
an empty directory. `mkdir(parents=True)` past a symlinked ancestor is
already a boundary violation. Confirm the walk uses `lstat`, not `realpath`,
and that no containment failure is retried.

Attack the *input* validation too, on both platform families. `materialize_under_root` originally used a hand-rolled `is_absolute()`, which is False on Windows for `Path("/etc")` (root, no drive); it now uses `atlas_contracts.paths.safe_relative_path`. Push `/etc`, `C:evil`, `../outside`, `a/../../b`, `con`, `trailing.` and `trailing ` through it and confirm each is rejected *and* that nothing is created for a rejected path.

In every blocked case the raw evidence must still be readable via
`atlas capture show` and its hash must still verify.

### V5 — Atlas-3 CLI guard

Against the real `src/project_atlas/cli.py`:

| mutation | expected |
| --- | --- |
| delete `register_atlas3_parsers(subparsers)` | FAIL |
| delete `dispatch_atlas3(args)` | FAIL |
| rewire a hook to a nested parser | FAIL |
| add a second seam call site | FAIL |
| re-point the import away from `project_atlas.atlas3.cli` | FAIL |
| `subparsers.add_parser("pulse")` in `cli.py` | FAIL (seam bypass) |
| add an unrelated nested subcommand | PASS, without any Atlas-3 hook in the diff |
| add an unrelated top-level command not in `ATLAS3_COMMANDS` | PASS |
| delete or rename an existing command registration | FAIL |
| unmutated file | PASS |

Also check the remediation did not merely relax: `test_g6b_...` asserts a diff
the **superseded** text-match contract accepted and the current one rejects.

### V6 — Source lineage

From a note, read `atlas.capture_id`, resolve
`generated/ops/raw-captures/<id>.json`, recompute the content hash from
`<id>.txt` and confirm it matches the record and the note frontmatter, then
confirm `project_id` names a real directory under `projects/`. Confirm the
capture is **not** in `generated/ops/inbox/` and asserts
`authority.level = quarantined-evidence`.

## Known limitations to confirm, not to fix

- No localhost capture API and no browser extension. `LIVE_API` is contractually
  read-only; `source_adapter` already accepts `"api"` so the seam is ready.
- No summarization or enrichment. The note prints `UNKNOWN` for
  Summary/Decisions/Actions rather than inventing them.
- Captures are never promoted into the Truth Core.
- `captured_at` is operator-supplied or absent — Atlas never generates a
  wall-clock value (NFR-001).
- Pre-existing and unrelated: `atlas validate --vault <relative-path>` fails a
  subpath check; reproduces without any captures.
- Recorded NONBLOCKING by the previous verifier and **out of scope** for R1:
  a governance obfuscation-class bypass, and secret shapes outside the
  contracted `project_atlas.secrets` pattern set. Do not treat either as
  fixed — they were not in scope, not that they were addressed.
