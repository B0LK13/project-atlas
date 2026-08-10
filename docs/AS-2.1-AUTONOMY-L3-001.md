# AS-2.1-AUTONOMY-L3-001

Bounded L3 autonomy enablement requiring:

1. AUTHZ capability `autonomy.l3`
2. Active supervised scheduler arm receipt (`AS-2.1-SCHED-LIVE-001`)

L4/L5 remain false. `vault_write_enabled=false`. Does not stamp RELEASE CERTIFIED
and does not satisfy authentic estate PILOT.

AS-2.1-L3-JOB-MATRIX-ADV additionally fail-closes on scope expansion, arm
overlap, destructive jobs, stale/disarmed arms, receipt mismatches, and
duplicate dispatch within one loop.
