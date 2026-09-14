# Prime Local 001 resource and provider inventory

Observed on 2026-09-14 in the candidate worktree. This is an inventory, not a
provider grant.

| Item | Observation | Consequence |
| --- | --- | --- |
| CPU | 8 logical CPUs | Suitable for bounded local canary work |
| Memory | 10 GiB total, 5.3 GiB available at probe time | No large local model is assumed |
| GPU | Intel Alder Lake-UP3 UHD Graphics; no discrete VRAM observed | No GPU-backed model selection |
| Local endpoint | Ollama reachable on `127.0.0.1:11434`; catalog empty | Local-only inference remains unavailable; no model manifest exists |
| Environment names | `ANTHROPIC_API_KEY`, `GITHUB_TOKEN` present by name only | Not imported, logged, or treated as a Prime grant |
| Prime credential grant | No current Atlas grant found for Prime real-model execution | Real-model validation remains open |
| Existing mission processes | Separate cached Atlas deployment processes observed | Not adopted or modified |

The adapter's local-only profile requires a loopback endpoint, an explicitly
advertised model, no credential environment, and no cloud fallback. A reachable
empty catalog therefore fails closed before inference. Provider cost is not
reported as zero; real-model validation is `not-run`.

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
