# Ask Atlas prompts — hero corpus

> **DEMO** · **NOT AUTHENTIC PILOT** · **NOT RELEASE EVIDENCE**

## Positive (evidence present)

**Q:** What HTTP port does Project A expose?

**Expected:** Answer referencing Project A architecture evidence (port 8080)
plus provenance — not invented UI copy.

## Unknown (evidence absent)

**Q:** What is Project C’s primary p99 SLO target?

**Expected:** `UNKNOWN` (explicit unknown in `project-c/INVENTORY.md`).

## Conflict (disagreeing evidence)

**Q:** Which PostgreSQL major version does Project A use?

**Expected:** `CONFLICT` / insufficient authoritative resolution —
docs say 15, implementation says 16. Do **not** silently pick either.
