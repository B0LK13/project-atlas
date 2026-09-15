# Loop skills

Agent playbooks the governed RSI loop may improve (`autonomy/policy.md` section 4:
`autonomy/instruments/skills/**` is an allowed scope from phase 0).

One skill per file, `<kebab-name>.md`, with:

- **When:** the trigger situation in one line.
- **Steps:** concrete and ordered, with exact commands.
- **Evidence:** what the step must leave behind for the packet.
- **Origin:** the `autonomy/packets/RP-<n>.md` reflection that motivated the skill.

A skill may add rigor or remove wasted motion. It may not relax a policy rule, skip a
lane, or reinterpret a verdict: authority lives in `autonomy/policy.md`, not here.
