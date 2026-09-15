# Prime Local 001 resource and provider inventory

## Resumed 1.7B bounded pilot

The authorized smaller model was exercised with an explicit
`PRIME_AGENT_KERNEL_PYTHON` pointing at a disposable copy of the existing
kernel environment. The worker namespace mounted the mission-owned config and
started the narrow TCP-to-Unix relay; no cloud credential was present.

Attempts `kernel-bound-rpc-1` through `-3` were fixture/configuration failures;
`-5` reached the host proxy but timed out with an uncertain `BrokenPipeError`.
Attempt `-6` completed one real 1.7B inference after 111.18 seconds, with
2,803 total reported tokens (753 output) and a confirmed Prime `agent_end`.
The model produced reasoning text only: no RLM/ipython toolcall, workspace
change, test run, child admission, or accepted coding result was observed.
Real-model reachability is proven, but the required real development slice and
end-to-end acceptance remain open.

The targeted follow-up `kernel-bound-capability-2` added the documented
Ollama OpenAI-compatibility control `reasoning_effort: none` at the proxy. The
request still did not yield an `ipython` toolcall: the proxy recorded a
connection reset and the bounded 180-second attempt ended uncertain. This
configuration correction has no completed assistant response in the stored
transcript, so its tool-use outcome is unknown; no further smaller-model
attempts are authorized by the owner decision.

The follow-up capability-only attempt `kernel-bound-capability-1` used the
same 1.7B model and explicit kernel interpreter. Stored-transcript inspection
for AS-PRIME-TOOLCALL-DIAGNOSTICS-001 corrects the earlier inventory: it contains
a valid structured `ipython` call, an execution-start event, and a kernel
startup error result. The configured interpreter lacked the required current
Prime runtime. The adapter's uncertain/transport-terminal outcome remains
unchanged; this is not a successful capability or coding result.

## Stored-evidence diagnostic correction (AS-PRIME-TOOLCALL-DIAGNOSTICS-001)

Inputs were read only from `/tmp/atlas-prime-pilot.JF33Zo/evidence/`.
Each transcript below is `<attempt>/<attempt>.prime-rpc.jsonl`. No inference,
kernel launch, or execution of recorded shell/Python payloads was performed.

| Attempt | SHA-256 | Records | Diagnostic |
| --- | --- | ---: | --- |
| `kernel-bound-rpc-6` | `7207d095da8b35ee9f7e12af75f0506b633cbb7924d747b47e154f413ceeaa2c` | 639 | `no_structured_toolcall` |
| `kernel-bound-capability-1` | `00a458ab5583ccdf350c09960a0052b6bb0fb950eb66b017ee6eb09df39fa6a1` | 336 | `kernel_start_failure`, structured call valid |
| `kernel-bound-capability-2` | `12580324ebb65f2600b3e224000e812010d494d6b693dbfa27dd12eac5e15be8` | 7 | `unknown` |

For capability-1, line 264 is `toolcall_end`; 266 is
`tool_execution_start`; 267 reports kernel starting; 268 is
`tool_execution_end` with `isError: true`; 270 is its persisted `toolResult`
message. The error specifically reports `PRIME_AGENT_KERNEL_PYTHON` pointing
to Python without the required current `prime-agent-runtime`. These are two
representations of one error result, not two successful executions.
Capability-2 has no completed assistant response: absence of a call in that
partial transcript cannot establish a model tool-use failure.

The additive control contract v3 exposes `last_attempt.toolcall_diagnostic`
for Prime attempts, derived only from their listed, bounded RPC/daemon
transcript files under the evidence root. Unavailable, malformed, oversized,
or conflicting evidence produces `unknown`. No task state, confidence,
acceptance, policy, or authorization is changed by this projection.

The parser distinguishes `tool_not_offered`, `no_structured_toolcall`,
`invalid_or_incomplete_toolcall`, `valid_call_rejected`,
`kernel_start_failure`, `tool_result_received`, and `unknown`. It targets the
pinned Prime `ipython` schema (an object with string `code`). Valid calls
without a result retain outcome `unknown`; execution-start and prompt ACK
are not success. `tool_result_received` means a structured result arrived,
including an unclassified error; its `is_error` flag is retained. Rejection
requires a matching valid call and the runtime's explicit default blocked
result. Arbitrary error prose is not classified as a policy rejection.

`tool_offered` remains unknown for these transcripts: neither an Ollama
catalog's tool capability nor a relay `forwarded`/transport-error audit proves
which tools were in the actual request. The pure stored-request helper can
distinguish an omitted/empty tools array from an offered `ipython` function.
Stored OpenAI response objects and decoded SSE data objects are accepted as
parser input, with argument fragments assembled by choice/tool index and
requiring terminal `tool_calls` evidence. Raw HTTP/SSE transport is not
replayed or newly captured. The proxy's forwarding and security logic is
unchanged.

## Supervisor result binding

The supervised result is bound to candidate HEAD
03bc4459c3b3ec35f400928ecf37b3baaaab6b50 and candidate worktree
TREE 08668fa840b4535b4b66717d32eef54161022612 at
/home/gebruiker/.cache/atlas-r-deploy/prime-local-001/diagnostics-001/workspace.
The current integrator worktree, including this result-binding record,
has derived TREE fdef392fb4a61d8b194f241a3b09a78cdaafa4f6.
The durable dispatch identity is:

| Field | Value |
| --- | --- |
| Program | atlas-prime-toolcall-diagnostics-001-successor |
| Task | AS-PRIME-TOOLCALL-DIAGNOSTICS-001 |
| Attempt/run | atlas-prime-toolcall-diagnostics-001-successor.AS-PRIME-TOOLCALL-DIAGNOSTICS-001.run.1.59cab7d5 |
| Agent / adapter | codex-diagnostics-001 / codex |
| Runtime session | 01a0a1b8-848b-77d0-82a2-778662c012b1 |
| Upstream / adapter | 5d25a44bd22e1c1fe8321e141cd6c3932563d14c / prime-agent-atlas-adapter-v2 |
| Profile digest | 6c3a2f96b7ef9701db6e9d333333907b596ec81a8da4d0d089384cc1ec828c1d |
| Outcome | worker exit_status=0; supervisor acceptance=false |

The supervisor's persisted usage receipt reports 2,477,957 input
tokens, 18,803 output tokens, and 4,001 reasoning-output tokens for
this attempt. The separately reported operator-turn figure 181,597 was
not present in any searched canonical deployment ledger and is therefore
not silently attributed to this Prime attempt or counted a second time.
No billed dollar amount is inferred.

Regressions embed minimized stored capability-1 events. Missing-tools,
plain-text, fragmentation, invalid-schema, rejection, and non-error-result
variants are explicitly synthetic parser fixtures, not additional pilot
outcomes. Diagnostic output excludes argument values, model prose, and raw
error messages. All pilot acceptance and release boundaries remain open.

Validation in the declared diagnostics workspace: **69 passed, 4 failed**
across the three listed test files. All new diagnostic regressions passed.
The four failures are existing socket tests: child-admission broker binding,
the two daemon-client tests, and proxy forwarding. Unix socket bind/connect
and TCP socket creation receive `PermissionError: [Errno 1] Operation not
permitted` in this sandbox (the daemon fixture readiness assertions then
time out). No security policy was changed to make them pass.

The declared `/home/gebruiker/.cache/atlas-r-deploy/runtime-008/bin/python`
initially rejected the coverage options because it lacks `pytest-cov`.
The complete suite was then run with that same interpreter, loading the
already installed plugin from the existing dev environment; no package was
installed. Reproduction of the final test run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
/home/gebruiker/.cache/atlas-r-deploy/runtime-008/bin/python - <<'PY'
import sys
sys.path.append('/home/gebruiker/.cache/atlas-r-deploy/continuation-completion-002-NCrqj3B3/dev-env/lib/python3.12/site-packages')
import pytest
raise SystemExit(pytest.main([
    '-q', '-o', 'addopts=',
    'tests/unit/test_prime_agent_adapter.py',
    'tests/unit/test_prime_inference_proxy.py',
    'tests/unit/test_orchestration_program_control.py',
    '--no-cov', '-p', 'no:cacheprovider', '--tb=short',
]))
PY
```

Focused Ruff checks on the six Python files, strict mypy on the three source
files, and `git diff --check` passed. Pre-existing workspace changes were
preserved, including the out-of-scope runtime manifest and relay script.
The patch does not claim a passing full acceptance gate or a managed-session
receipt; governance/taskstore writes are outside this task's mutation scope.

Observed on 2026-09-14 in the candidate worktree. This is an inventory, not a
provider grant.

| Item | Observation | Consequence |
| --- | --- | --- |
| CPU | 8 logical CPUs | Suitable for bounded local canary work |
| Memory | 10 GiB total, 5.3 GiB available at probe time | No large local model is assumed |
| GPU | Intel Alder Lake-UP3 UHD Graphics; no discrete VRAM observed | No GPU-backed model selection |
| Local endpoint | Ollama reachable on `127.0.0.1:11434`; catalog advertises `qwen3:4b` | Host catalog is reachable, but the reviewed Bubblewrap worker profile intentionally cannot reach host loopback |
| Environment names | `ANTHROPIC_API_KEY`, `GITHUB_TOKEN` present by name only | Not imported, logged, or treated as a Prime grant |
| Prime credential grant | Pilot attachment authorizes only local `qwen3:4b`, with no cloud fallback or token import | Provider choice is authorized for the bounded pilot; the inference route still requires a reviewed narrow proxy/IPC bridge |
| Existing mission processes | Separate cached Atlas deployment processes observed | Not adopted or modified |

The pilot model artifact was downloaded by the existing Ollama service with the
operator-authorized command `ollama pull qwen3:4b`. Ollama reported model digest
`359d77...74fae7`, size `2,497,293,931` bytes (2.5 GB), and the model metadata
reports Qwen3, 4.0B parameters, GGUF/Q4_K_M, 262,144 context, and tool
capability. The model declares Apache-2.0 licensing. These are artifact facts,
not proof that Prime executed inference.

The adapter's local-only profile requires a loopback endpoint, an explicitly
advertised model, no credential environment, and no cloud fallback. The host
catalog now satisfies the advertisement check, but the reviewed worker profile
still blocks host loopback. Directly weakening that profile would expose
Ollama's management API and is not an accepted pilot route. A narrow
mission-owned inference proxy/IPC bridge with management endpoints denied must
therefore be implemented and tested before real-model validation. Provider cost
is not reported as zero; real-model validation is `not-run`.

The inference-only proxy itself was live-tested through an unshared-network
Bubblewrap namespace: `/v1/models` returned the local catalog and `/api/pull`
returned HTTP 403. A Prime client-owned run then started the real Prime/RLM
process chain, but CPU-only generation exceeded the pilot's resource safety
boundary: host available memory fell to approximately 0.5 GiB while the
process group remained active. The run was stopped by explicit process-group
termination; no workspace mutation or accepted toolcall was recorded. The
shared Ollama service was not restarted or administratively changed.

The bundled (`--dist`) Prime launcher was then tested under the user-level
systemd scope with `MemoryMax=6442450944`, `CPUQuota=400%`, and
`TasksMax=256`. It reduced launcher overhead, but the host's available memory
still fell to approximately 1.9 GiB during model initialization. The pilot
was stopped at that boundary and remains unaccepted; the cgroup boundary is a
resource control, not evidence that the real-model task succeeded.

The separately authorized `qwen3:1.7b-q4_K_M` artifact was downloaded from the
official Ollama library at 1,359,293,444 bytes and is pinned locally by full
digest `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`.
Ollama reports Q4_K_M, 2.0B parameters, 40,960 model context, and
`completion/tools/thinking` capabilities under Apache-2.0. With this model,
the cgroup-constrained Prime chain stayed at roughly 3.1–3.6 GiB available
host memory, but both client-owned and resident routes timed out after
starting the Prime daemon/worker and before an inference audit event. No
toolcall, patch, or accepted coding result was produced; all pilot processes
were terminated and the shared service was not restarted.

Safety incident during validation: the upstream aggregate `npm test` command
contains provider E2E tests and was stopped after it attempted Anthropic calls
(HTTP 400: insufficient credit) and began an unintended Ollama model pull.
All test processes were stopped and `ollama list` remained empty. The exact
partial blob is owned by the `ollama` service account under
`/usr/share/ollama/.ollama/models/blobs/` and could not be removed without
interactive service-owner/root authorization. Cleanup resume condition: an
authorized operator removes only the timestamp-matched
`sha256-e7b273...-partial*` files after confirming no pull is active. No Prime
inference or provider grant was claimed from this incident.
