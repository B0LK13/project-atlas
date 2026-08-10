# Harbor API — Architecture

> DEMO FIXTURE — NOT AUTHENTIC PILOT — NOT RELEASE EVIDENCE

## Data store

Harbor API uses **PostgreSQL 15** as the system of record for tenant
metadata and session tokens.

## Components

- HTTP JSON API on port 8080
- Background worker for webhook delivery
- Shared library package consumed by Harbor Portal

## Notes

This document is intentional architecture **documentation** evidence for the
demo conflict scenario (compare with `src/RUNTIME.md`).
