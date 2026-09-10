# Hook Diagnosis 007

## Ownership and evidence

- The Codex session hook is configured in `/home/gebruiker/.codex/hooks.json` under `SessionStart` and `Stop`.
- Its command uses the absolute interpreter `/usr/bin/python3` and the script `/home/gebruiker/Documents/Codex/2026-09-05/create-a-scheduled-task-called-weekday/outputs/developer-hooks.py`.
- Running that command with representative `SessionStart` and `Stop` JSON from the isolated worktree returned exit 0. It is an auxiliary context/notification hook; it does not gate execution.
- The repository hook is configured in `.cursor/hooks.json` under `stop` and `beforeSubmitPrompt`. Both commands invoked the bare `python` name, which is absent from the effective shell lookup path (`zsh: command not found: python`).

## Repair and validation

Both repository hook commands now invoke `python3`, preserving the same scripts and arguments. From the repository root, representative Stop and before-submit invocations returned exit 0 with the expected `{}` and `{"continue":true}` outputs. No governance behavior, approval behavior, or global configuration was changed.

The original “Hook failed, exited with code 127” therefore belonged to repository Cursor tooling (or a host that executes `.cursor/hooks.json`), not the Codex hook. The missing executable was the bare `python` command. Native display diagnosis remains separate; this repair does not establish native interaction.
