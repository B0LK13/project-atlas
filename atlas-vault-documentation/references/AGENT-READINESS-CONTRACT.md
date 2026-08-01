# Agent readiness contract

An adapter is authorized for governed work only when its registry entry matches the operational skill version and SHA-256, is not revoked, and has `rehearsal_status: passed`. A missing, stale, pending, or revoked entry is a fail-closed condition for strict managed execution. Read-only advisory agents may be listed as not-applicable and cannot own a completion receipt.
