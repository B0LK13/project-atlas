# AS-ORCH-SPECULATIVE-CERTIFICATION-001

## Mission

Make the successful D-121/D-122 protocol a first-class durable Atlas orchestration capability:

1. candidate seal (HEAD/TREE/BASE_MAIN/generation)
2. parallel certification lanes with exact-pin binding
3. tip-drift cancellation (no in-generation repair)
4. exact-pin evidence promotion
5. merge remains owner-held (`merge_authorization = NOT_GRANTED`)

## Boundary

- Package id: `AS-ORCH-SPECULATIVE-CERTIFICATION-001`
- Base main at allocation: `fa129ff4ccdc099d83345edcc99d547ca5d907ac`
- Branch: `feat/as-orch-speculative-certification-001`
- Coordinator: primary Atlas CLI governor only
- Disposable workers may implement/verify; governor owns DAG

## Non-goals

- Auto-merge
- Changing AS-ORCH-CONTINUATION-BROKER-001 semantics beyond reuse
- Repairing a drifted tip inside a frozen generation

## Pipeline

implement → independent verification → adversarial verification → certification → OWNER_HELD_MERGE_ELIGIBLE
