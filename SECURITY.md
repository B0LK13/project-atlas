# Security Policy

## Supported versions

Project Atlas is pre-1.0 (`pyproject.toml` currently declares `0.1.0`) with
no tagged releases yet. There is no maintained release branch model; the
only supported target is the current `main`.

| Version | Supported |
| ------- | --------- |
| `main`  | Yes       |

## Reporting a vulnerability

External private vulnerability intake is **not currently operational** for
this repository. GitHub's native private vulnerability reporting is not
currently available on this repository's plan.

- Do not open an ordinary public GitHub issue for a suspected
  vulnerability. Sensitive vulnerability details must not be placed in
  ordinary GitHub issues.
- Authorized collaborators should use an already-established private
  communication channel with the repository owner.
- External (non-collaborator) reporting is deferred. There is currently no
  published external reporting address, alias, or form, and none is
  invented here — no personal email address, placeholder contact form, or
  unverified reporting URL is published in this policy.
- A future external reporting channel requires separate Project Owner
  provisioning, verification, and authorization before it can be
  published. Until then, this section will be updated to point at it.

## Response expectations

This is a best-effort, small-maintainer project. No guaranteed response
time or service-level commitment is made for any report.

## Handling process

Confirmed vulnerabilities are addressed on a bounded branch or PR before
any public disclosure of exploit details, following this repository's
existing evidence-based work-package discipline
(`docs/evidence/*.yaml`) for the fix's own record.

## Scope

This policy covers this repository's own code and configuration. Issues in
third-party dependencies should be reported upstream to the relevant
project first.
