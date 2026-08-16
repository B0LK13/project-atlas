# Cloud IV runbook — AS-CODER-ALPHA-NEXT-API-001

**Package:** `AS-CODER-ALPHA-NEXT-API-001`  
**Branch:** `cursor/next-api-001-5408`  
**Base:** `origin/main` `32c992894d7cabe58dd4b965585093fe6d308458`  
**SIMULATION_ONLY for #365/#366:** this package does not depend on those merges.

## Honesty

- `CLOUD_IV` may be recorded only after the commands below pass on this HEAD.
- `LOCAL_IV = NOT_RUN` unless a Local operator executes the Local section.
- `AUTHENTIC_ESTATE = NOT_CLAIMED`
- `WINDOWS_AUTHENTIC = NOT_CLAIMED`
- NEXT LENS != AUTHORITY / NEXT ACTION != COMMAND

## Cloud IV (this environment)

**Recorded on HEAD** `7c7c97f88e70f019deb38bd8dc9a7a5273cf7f4a`  
**TREE** `abf775acf89d548b85e3e9467a338825bc033e0d`  
**CLOUD_IV = PASS** (2026-08-16 Cloud agent; not Local)

```bash
.venv/bin/python -m ruff check src tests          # exit 0
.venv/bin/python -m mypy src                      # exit 0; 219 files
.venv/bin/python -m pytest --no-cov \
  tests/unit/test_as_coder_alpha_next_api_001.py  # 5 passed
.venv/bin/python -m pytest \
  tests/unit/test_as_coder_alpha_next_api_001.py \
  tests/unit/test_as_coder_alpha_next_001.py \
  tests/unit/test_as_coder_alpha_source_health_api_001.py \
  tests/unit/test_as_2_0_mcp_001.py \
  tests/unit/test_as_sec_009_api_auth.py           # 30 passed
```

`tests/unit/test_as_2_1_mcp_brief_001.py` is not on current `main` (lives on owner-held `#365`). It was run on the disposable `CURRENT_MAIN + #365 + this package` tree and passed (46 tests with neighbors).

Pass criteria:

- ruff 0
- mypy 0
- pytest 0
- `/v1/next` requires `project`
- unknown project is fail-closed
- empty project returns UNKNOWN, not invented work
- harbor response does not contain portal secrets
- PATCH `/v1/next` is 405 and vault bytes are unchanged
- `generated/answers/` is not created

## Local runbook (prepare only — do not stamp PASS here)

Owner/Local only, after Cloud IV PASS:

1. Checkout the exact package HEAD/TREE (do not use this runbook as a merge grant).
2. Repeat the Cloud IV commands on the Local machine.
3. Against a Local bound vault (`atlas connect` already done):

```bash
atlas next --vault <vault> --project <id> --json
# then LIVE_API
atlas live api-serve --vault <vault>
# GET /v1/next?project=<id> with session Bearer
```

4. Confirm CLI JSON `project_id` / `primary` / `honesty.next_is_command=false`
   match the API payload (UI/API != canonical; compare derived fields only).
5. Confirm a second project id cannot read the first project's next queue.
6. Do **not** record `LOCAL_IV=PASS` from Cloud. Windows authentic remains
   separate.

## Post-365 compatibility

This package is independent of `#365`. Optional disposable check after
`CURRENT_MAIN + PR365` simulated tree `be7dbe04cab8f71b97a9d746ee417db8e8ddeda2`:

```bash
PYTHONPATH=<this-branch-src> .venv/bin/python -m pytest \
  tests/unit/test_as_coder_alpha_next_api_001.py \
  tests/unit/test_as_2_1_mcp_brief_001.py
```

Do not rebase or rewrite `#365` / `#366`.
