# Receipt contract

A successful receipt contains the session, task, project, agent, adapter, acknowledged skill ID/version/hash, mandatory event IDs, pipeline counts, validation status, Vault identity, and synchronization state. A receipt is written only after strict validation and is immutable by content. Missing acknowledgement, stale adapter readiness, pending strict spool, missing mandatory events, or incomplete pipeline accounting prevents completion.
