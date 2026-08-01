# Command surface

Use `atlas-agent bootstrap`, `acknowledge-skill`, and `capability-check` before project mutation. Use `document` for events; use `validate`, `receipt`, and `postflight` for completion. Internal capture, normalization, verification, and routing commands are not agent APIs.

All commands accept `--json` for automation. Resolve context from the active session rather than duplicating Vault paths.
