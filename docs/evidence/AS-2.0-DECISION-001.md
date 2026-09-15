# AS-2.0-DECISION-001 — Decision support core

Library-only decision candidate model.

Represents:

- decision question
- known evidence
- unknowns
- conflicts
- options
- constraints
- evidence gaps
- reversible / irreversible only when explicitly claimed

Never selects a correct decision.

`DECISION_CANDIDATE_IS_COMMAND = NO`
`DECISION_ENGINE_IS_AUTHORITY = NO`

`DECISION CANDIDATE ≠ COMMAND / ≠ SELECTED TRUTH / ≠ AUTHORITY`
