# AS-DEMO-2.1-001 — Optional L3 loop + OAI Responses POC

**TECHNICAL DEMO — VERIFIED** path only.
**NOT RELEASE CERTIFIED** · **NOT AUTHENTIC PILOT PASS** · **PILOT DORMANT**.

| Field | Value |
|---|---|
| Package | `AS-DEMO-2.1-001` optional lane |
| Surfaces | Bounded L3 loop (`AS-2.1-AUTONOMY-L3-001`) · OAI Responses POC (`AS-2.1-OAI-RESPONSES-POC-001`) |
| Blocking | **NON_RELEASE_BLOCKING** — optional; skip without failing Technical Demo certification |
| Estate | **DEMO_FIXTURE only** (`ATLAS_DEMO_MODE=fixture`) — never authentic pilot roots |
| OAI honesty | Record `LIVE_SMOKE_RATE_LIMITED` / offline / HTTP errors **as-is**; do not upgrade to PASS |
| Authority | `llm_authority=false` · `vault_write_enabled=false` · L4/L5 remain false |

> Banner: **DEMO ≠ AUTHENTIC PILOT ≠ RELEASE EVIDENCE**.  
> Success here never implies `ATLAS_2_1_RELEASE_CERTIFIED` or authentic estate PILOT.

---

## When to run

Run this lane **only** when an operator wants an optional supervised-ops / experimental-provider demo.

- Core Technical Demo (fixture backend, Web, API/MCP) **must not depend** on this file.
- Missing `OPENAI_API_KEY`, HTTP 429 (`RATE_LIMITED`), or skipped L3 arm setup → document outcome and continue; **do not** invent pilot pass language.
- Prefer a disposable DEMO vault under `docs/demo/fixtures/` (or a temp path labeled `DEMO_FIXTURE`). Never invent `.atlas-project.yaml` inside a real project to fake pilot status.

---

## Prerequisites (shared)

```powershell
# From a clean clone / worktree of project-atlas
pip install -e ".[dev]"
$env:ATLAS_DEMO_MODE = "fixture"

# Disposable DEMO vault (example)
$DemoVault = Join-Path $PWD ".tmp\demo-l3-oai-vault"
atlas init --output $DemoVault
```

Confirm the session banner (or print explicitly):

```
TECHNICAL DEMO — VERIFIED
NOT RELEASE CERTIFIED
NOT AUTHENTIC PILOT PASS
NON_RELEASE_BLOCKING optional lane: L3 + OAI Responses POC
```

---

## Part A — Optional bounded L3 loop

### Truth boundary

- Requires AUTHZ capability `autonomy.l3` and an **active** supervised scheduler arm.
- Allowed jobs only: `validate`, `build-indexes`, `version`.
- Denied: `ingest`, `discover`, `init`, `promote`, `migrate`, `sync`, `delete`, `quarantine`, and any L4/L5 enablement.
- Loop writes a receipt under `generated/ops/autonomy/<policy-id>-l3-loop.json` with `promoted: false` and `vault_write_enabled: false`.

### Demo steps

1. **Arm supervised scheduler** (DEMO vault only):

```powershell
atlas live sched-arm --vault $DemoVault --arm-id demo-arm-l3 --json
```

2. **Enable bounded L3 policy** (Python API — no CLI enable surface yet):

```powershell
python -c @"
from pathlib import Path
from project_atlas.authz import elevated_operator
from project_atlas.autonomy_l3 import enable_bounded_l3
vault = Path(r'$DemoVault')
op = elevated_operator('demo-l3-op', extra={'autonomy.l3'})
print(enable_bounded_l3(vault, policy_id='demo-pol-l3', arm_id='demo-arm-l3', operator=op))
"@
```

3. **Run one bounded loop** (CLI):

```powershell
atlas live l3-loop --vault $DemoVault --policy-id demo-pol-l3 `
  --job version --job validate --json
```

4. **Inspect receipt** — expect `l3_loop: true`, `levels_enabled.4/5: false`, `promoted: false`:

```powershell
Get-Content (Join-Path $DemoVault "generated\ops\autonomy\demo-pol-l3-l3-loop.json")
```

5. **Optional fail-closed spot-check** (ADV language, not release gate): repeat `--job version` twice in one invocation, or pass a denied job via a crafted policy — expect non-zero exit / `AutonomyL3Error`. Do **not** treat ADV failure as release evidence.

### Honest outcomes

| Outcome | Demo language |
|---|---|
| Loop receipt written, jobs exit 0 | Optional L3 DEMO step **shown** |
| Missing arm / capability / policy | Skip with note — **NON_RELEASE_BLOCKING** |
| Fail-closed ADV reject | Expected hardening — still **not** PILOT / release |

---

## Part B — Optional OAI Responses POC

### Truth boundary

- EXPERIMENTAL · **NON_RELEASE_BLOCKING**.
- `llm_authority=false`; output quarantined (`quarantine_provider_output`).
- Read-only AppService tools only: `atlas_health_read`, `atlas_projects_list`, `atlas_knowledge_list`, `atlas_graph_summary`.
- No write / promote / Layer B tools.
- `OPENAI_API_KEY` from environment only (never logged or committed).
- Capability: `oai.responses`.

### Demo steps

1. **Offline-first (default honest path — no key required):**

```powershell
atlas live oai-responses-poc --vault $DemoVault --run-id demo-oai-offline `
  --prompt "Summarize vault health with read-only tools" --force-offline --json
```

Expect `smoke_status: IMPLEMENTATION_READY_FOR_LIVE_SMOKE` (or equivalent offline-ready status) and `live_smoke: false`.

2. **Optional live smoke** (only if operator supplies a key):

```powershell
# Do NOT paste the key into docs, logs, or receipts.
# $env:OPENAI_API_KEY = "<from secret store>"
atlas live oai-responses-poc --vault $DemoVault --run-id demo-oai-live `
  --prompt "Summarize vault health with read-only tools" --json
```

3. **Read the POC receipt** (never treat model text as authority):

```powershell
Get-Content (Join-Path $DemoVault "generated\ops\oai-responses-poc\demo-oai-live-poc.json")
```

### RATE_LIMITED honesty (mandatory)

Record the **actual** `smoke_status` from the receipt:

| `smoke_status` | Allowed demo claim |
|---|---|
| `IMPLEMENTATION_READY_FOR_LIVE_SMOKE` | Offline POC path verified |
| `LIVE_SMOKE_EXECUTED` | Live smoke executed (still NON_RELEASE_BLOCKING; still ≠ PILOT) |
| `LIVE_SMOKE_RATE_LIMITED` | **RATE_LIMITED** — say so; do not retry-spam; do not call it PASS |
| `LIVE_SMOKE_HTTP_ERROR` / `NETWORK_ERROR` / `FAILED` | Record failure class; optional lane incomplete |

Optional single retry only when `ATLAS_OAI_POC_RETRY=1` is explicitly set by the operator. Never hide 429 behind success language.

### Forbidden claims

- Do **not** say RELEASE CERTIFIED, authentic PILOT PASS, or “LLM decided Layer B”.
- Do **not** promote quarantined POC output into canonical concept notes.
- Do **not** use live OAI results as release-gate or PILOT evidence.

---

## Demo checklist (optional lane)

- [ ] Banner shown: TECHNICAL DEMO — VERIFIED / NOT RELEASE CERTIFIED / NOT AUTHENTIC PILOT
- [ ] Vault path labeled DEMO_FIXTURE / disposable demo vault
- [ ] L3 skipped **or** loop receipt shows `promoted: false`, L4/L5 false
- [ ] OAI skipped **or** receipt `smoke_status` recorded honestly (including `LIVE_SMOKE_RATE_LIMITED`)
- [ ] No authentic-estate markers invented
- [ ] Operator explicitly acknowledges **NON_RELEASE_BLOCKING**

---

## References

- `docs/AS-2.1-AUTONOMY-L3-001.md`
- `docs/AS-2.1-OAI-RESPONSES-POC-001.md`
- `docs/atlas-2.1/ADV-LIVE-SUITE.md` (L3 ADV matrix — adversarial, not release cert)
- Charter / mode banner (D01): `docs/demo/AS-DEMO-2.1-001.md`, `docs/demo/MODE-BANNER.md` when present

---

## Certification note

Completing this optional lane may support **TECHNICAL DEMO — VERIFIED** storytelling only.
It does **not** move Atlas 2.1 toward RELEASE CERTIFICATION and must **never** be filed as authentic estate PILOT.
