# supervisor-concurrency-008 — branch note (allowlist + analysis)

Base: fc69f9d623a73a1880371dd947ba5adf9139666b (candidate pin, unchanged).

## Findings

1. A22 serialization (measured in completion-007) is NOT a source defect:
   the installed package is byte-identical to this source (diff of
   `orchestration/program/supervisor.py` = 0 lines), and the cycle fill loop
   already submits each dispatch and waits for the FIRST worker only after
   the loop.
2. Root cause of the observed serialization: `surfaces_overlap`
   (`autonomy/overlap.py`) also compares `MutationSurface.semantic`. All
   007 fixture tasks shared `surface_semantic="FIXTURE_PROBE"`, so every
   task pair overlapped and the overlap gate serialized the program. Tasks
   with distinct surface_id + distinct semantic + disjoint paths are
   eligible for true parallel dispatch under `max_concurrent_workers`.
3. Idle CPU: the resident dispatcher already sleeps in wake quanta
   (`request_wake`/`consume_wake`, quantum 0.5 s, default tick 5.0 s);
   007 measurements passed `--tick-seconds 0.5` explicitly, which is what
   kept idle CPU at ~1.2-1.3 %. The supported default configuration is
   expected to meet <1 % with wake p95 well under 2 s (measured in 008).

## File allowlist for this branch

- Intended: `src/project_atlas/orchestration/program/supervisor.py`,
  `src/project_atlas/orchestration/program/resident.py`,
  `src/project_atlas/orchestration/autonomy/overlap.py`.
- Actual change required: none (existing equivalent implementation kept,
  per plan rule). This note is the branch's only content.
- If a future measurement contradicts the findings above, changes are
  confined to the allowlist and carry their own regression gates.
