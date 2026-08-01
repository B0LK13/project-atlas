# Document inventory contract

Inventory records are sorted by case-folded normalized relative path. SHA-256
is streamed from the source. Inventory hashes exclude volatile modification
timestamps. Sensitive and unsupported files remain visible as metadata-only
records and are never semantically imported.
