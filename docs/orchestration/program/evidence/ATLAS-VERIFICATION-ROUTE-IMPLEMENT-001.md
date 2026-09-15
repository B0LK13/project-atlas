# ATLAS-VERIFICATION-ROUTE-IMPLEMENT-001

Status: built and model-free tested; real independent verdict is `UNKNOWN`.

The implementation adds `ProgramTask.task_kind=VERIFY_SUBJECT` to the existing
program supervisor. It uses the ordinary loader, registry binding, lease,
dispatch intent, adapter, evidence and state machinery. A `VerificationSubject`
is frozen by exact subject HEAD/TREE, attempt, criteria digest, profile digest
and evidence digests. The verifier has no mutation paths. Its JSON is a
proposal; the supervisor evaluates the bound acceptance checks and publishes a
separate atomic, idempotent review receipt. The original attempt/state is not
written.

Operator readback is:

```sh
PYTHONPATH=src python -m project_atlas.orchestration.program.cli program reviews \
  --program /home/gebruiker/.cache/atlas-r-deploy/prime-local-001/verification-route-001/program.json \
  --state-root /home/gebruiker/.cache/atlas-r-deploy/prime-local-001/verification-route-001/state-v6
```

Frozen subject: attempt `atlas-prime-toolcall-diagnostics-001-successor.AS-PRIME-TOOLCALL-DIAGNOSTICS-001.run.1.59cab7d5`, HEAD `03bc4459c3b3ec35f400928ecf37b3baaaab6b50`, tree `08668fa840b4535b4b66717d32eef54161022612`. The original acceptance remains false; its cause was the historical runtime's unsupported pytest coverage addopts. The later review record is `eaa3a36ef59a95506890697762872f6421d65bbf688dacad1d9cf077555a5ca6` and binds engine `atlas-verification-route-v1` and reviewer `codex-prime-reviewer-001`.

Model-free result: 77 focused supervisor/control/verification tests passed.
The one authorized real reviewer launch was dispatched through the registry,
used Codex `0.154.0` OAuth in `--sandbox read-only`, and consumed one review
slot. Codex rejected the response schema before inference because the first
schema used JSON Schema `const` without a `type`; therefore no reviewer
content or the three requested trace diagnoses exists. The trusted receipt is
`UNKNOWN`, not green, and records the exact failure. The corrected candidate
program contains typed schema properties but was not relaunched, preserving the
one-launch grant.

Remaining gates: no independent content verdict, no acceptance of the
diagnostics task, no required human IV, no exact-head CI, no merge, no
production/service replacement, and no Vault receipt. The old coding attempt,
its false acceptance and its state remain unchanged. A future review requires
a fresh owner-approved review grant and a new review program identity; it must
not replay the uncertain/failed launch blindly.

## Schema repair follow-up

The first Codex launch used `/home/gebruiker/.local/npm/bin/codex`,
`codex-cli 0.154.0`, with `codex exec --json --sandbox read-only
--output-schema`. Codex returned `invalid_json_schema` at
`#/properties/review_engine_id`: the schema node had `const` but no `type`.
The offered schema hash was
`3db11dfbd67f99aec600fb532cd2ba465ae7abf540a37aa86033c01d23bd95e6`.

The minimal repair adds `type: string` beside both string constants and the
verdict enum. The actual launcher serializer now emits schema hash
`cab8e99a0368335228056bba1e799d5505e0c6a8d7c941cb33c7c1a18b556652` and runs
the same local recursive preflight before writing or passing `--output-schema`.
Nine focused verification tests pass, including original-schema rejection,
repaired-schema acceptance and nested/required failures.

The one new Codex review completed without schema error. Receipt
`8eb7e4533ac403d8f0ae5c5685db519ef4b617f9ecd336941f31cbee9010a6a2` is bound
to the same subject attempt, HEAD, tree and criteria, with verdict `FAIL`.
The reviewer found conflicting `Content-Length` headers after proxy body
rewriting, and JSON-body validation incorrectly applied to `GET /v1/models`.
No subject files or state changed. Usage was 250,812 input tokens, 211,328
cached input tokens, 1,889 output tokens and 136 reasoning-output tokens;
cost is UNKNOWN.

The three prior trace diagnoses remain separately bound: RPC-6
`no_structured_toolcall`, capability-1 `kernel_start_failure` after a valid
structured call, and capability-2 `unknown`. The reviewer did not establish
an acceptance PASS or independently confirm all three, so the subject remains
open.
