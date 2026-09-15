# Reality Gap — deepen fixture plan (PREP)

Package: **AS-2.2-REALITY-GAP-DEEPEN-PREP-001**

| Fixture | Kind | Expected |
|---|---|---|
| `negative-deepen-unknown-as-healthy.expect.json` | `unknown_as_healthy` | rejected_forbidden |
| `negative-deepen-ui-canonical-write.expect.json` | `ui_canonical_write` | rejected_forbidden |
| `negative-deepen-release-cert-stamp.expect.json` | `release_cert_stamp` | rejected_forbidden |
| `negative-deepen-unlock-stamp.expect.json` | `unlock_stamp` | rejected_forbidden |
| `negative-deepen-pilot-invent.expect.json` | `pilot_invent` | rejected_forbidden |
| `negative-deepen-runtime-mutation.expect.json` | `runtime_mutation` | rejected_forbidden |
| `negative-deepen-llm-authority.expect.json` | `llm_authority_stamp` | rejected_forbidden |

All deepen fixtures are **fixture-only**; they do not dual-own base `negative-*.fixture.json` peers.
