# Loop skills

Agent playbooks and role files (supervisor, executor, verifier, instrument) for the governed
RSI loop. The loop may edit `autonomy/instruments/skills/**` from autonomy level 1
(`autonomy/policy.md` sections 4 and 11); at level 0 skill edits are proposed in packets.

One skill per file, `<kebab-name>.md`, with:

- **When:** the trigger situation in one line.
- **Steps:** concrete and ordered, with exact commands.
- **Evidence:** what the step must leave behind for the packet.
- **Origin:** the `autonomy/packets/RP-<n>.md` reflection that motivated the skill.

A skill may add rigor or remove wasted motion. It may not relax a policy rule, skip a
lane, or reinterpret a verdict: authority lives in `autonomy/policy.md`, not here.
