# Ingestion receipt contract

An ingestion receipt records the immutable inventory and plan hashes, source
counts, processing counts, coverage, conflicts, Graphify deferral, transaction
identity, Atlas updates, validation status, and blockers. Repeating an
unchanged inventory reuses the existing receipt and performs no writes.
