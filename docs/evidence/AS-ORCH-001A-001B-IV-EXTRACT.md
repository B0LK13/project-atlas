# AS-ORCH-001A / 001B independent IV extract

**Base main:** `4e71cce0d1c97f408347e256300a41590da4c352`  
**Branch:** `cursor/atlas-autonomous-night-cycle-4926`  
**Source draft:** `#448` (`tests/integration/test_orchestration_iv_001a.py`, `…_001b.py`)  
**Merge authorization:** `NOT_GRANTED`

Extracts the already-written 001A/001B integration IV onto current main.
The extract author is not the 001A/001B implementer. Tests exercise the
real CLI classify/route chain: valid envelopes, MERGE_ELIGIBLE never
MERGE, tamper fail-closed, terminal/blocked non-dispatch, idempotent
revalidate.

Local result: 10 passed.
