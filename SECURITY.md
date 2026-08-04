# Security Policy

## Supported versions

Project Atlas is pre-1.0 (`pyproject.toml` version `0.1.0`) and has not
yet cut a tagged release. Only the tip of `main` is supported for
security fixes; there are no maintained release branches.

## Scope

In scope: `src/project_atlas/`, `src/atlas_contracts/`, and this
repository's GitHub Actions workflows and configuration
(`.github/`). `atlas-vault-documentation/` is a sibling deliverable
with its own tooling; findings against it are still welcome through
the same reporting path below.

Out of scope: vulnerabilities in third-party dependencies themselves
(report those upstream to the dependency's own maintainers first);
findings that require an already-compromised local machine or an
already-untrusted `atlas discover`/`ingest` source tree the operator
chose to scan.

## Reporting a vulnerability

**Private vulnerability intake is not currently operational for this
repository.** GitHub's private vulnerability reporting and secret
scanning / push protection features are unavailable under the
repository's current plan and have not been enabled.

Because of this:

- **Do not** open an ordinary public GitHub Issue containing
  vulnerability details, proof-of-concept exploit code, or any
  sensitive technical detail.
- If you are an authorized collaborator, use an already-established
  private channel with the repository owner instead of GitHub Issues.
- If you are an external reporter, external private intake is
  **deferred** until the Project Owner provisions and verifies a
  dedicated reporting channel (for example, GitHub's private
  vulnerability reporting once plan-available, or a dedicated
  security alias). No such channel is published today, and this
  document will be updated with the verified channel once one exists.
  Until then, please do not disclose vulnerability details publicly;
  check back on this file for an updated reporting path.

This document intentionally does not publish a personal email address,
alias, or other unverified contact channel.

## Response expectations

This is currently a single-maintainer project. No specific response
time or resolution SLA is promised, because none is operationally
supported today. Reports will be acknowledged and triaged on a
best-effort basis.

## Handling and disclosure

Confirmed vulnerabilities are fixed on a minimally-scoped branch/PR
before any public disclosure of exploit details. Fixes follow this
repository's existing evidence discipline (a `docs/evidence/AS-SEC-xxx-*`
receipt), the same pattern already used for the source-quarantine /
prompt-injection boundary (`docs/adr/ADR-004-source-quarantine-prompt-injection-boundary.md`).

## Existing compensating controls

Independent of GitHub's currently-unavailable security features, this
repository already has, and continues to rely on:

- content-based secret scanning and quarantine at ingestion time
  (`src/project_atlas/secrets.py`, `src/project_atlas/quarantine.py`);
- a deterministic, fuzz-tested prompt-injection/source-quarantine
  boundary (ADR-004);
- path-traversal protection on every write (`_inside()` guards in
  `src/project_atlas/ingestion.py`).

These do not replace GitHub-native scanning; they are documented here
so this policy does not understate the repository's actual current
security posture while GitHub-native features remain unavailable.
