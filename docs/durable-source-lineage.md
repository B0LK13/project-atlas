# Durable source lineage

The canonical source registry is `state/sources.json`, schema version 2. Each
logical source has an immutable `source_lineage_id` and positive immutable
`lineage_generation`; path and current content are mutable provenance and
observation fields. Retired records remain in the registry.

Project identity is a one-time UUIDv4 in `.atlas-project.yaml` or
`.atlas/project.yaml`. Production allocation uses a cryptographically strong
UUIDv4 provider. Tests inject a provider. The marker mutation, allocation
receipt, registry migration, and source state are validated in one write plan.

Canonical paths are project-relative, slash-separated, NFC-normalized,
case-sensitive, and reject absolute paths, drive letters, `.`/`..`, empty
segments, and symlinks. Content fingerprints are streaming SHA-256 hashes of
the original bytes.

Unchanged observations reuse the persisted identity. Modifications, renames,
moves, deletion, and proven restoration retain lineage. Equal-content copies
are independent. Multiple plausible retired candidates produce an unresolved
identity error and zero canonical writes. Known v1 state migrates in recorded
historical order and emits one `source-lineage-migration` receipt per migrated
lineage; unknown schema or malformed identity state fails closed.

The Core-local lock covers marker/registry reread, candidate selection,
preflight, write-plan construction, promotion, and release. It is not Vault
knowledge state and leaves no lock file after ordinary completion.
