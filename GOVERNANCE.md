# Commons Governance

Commons is an open-source project stewarded by T54 Labs.

## Roles

### Contributors

Anyone who submits issues, documentation, tests, code, design feedback, or
operational evidence is a Contributor.

### Maintainers

Maintainers review and merge changes, manage releases, respond to security
reports, and protect the product and trust boundaries described in the public
documentation. T54 Labs appoints the initial Maintainers.

Sustained Contributors may become Maintainers based on technical judgment,
constructive review, reliability, and demonstrated care for security and
compatibility. Maintainer access is never granted solely from contribution
volume.

## Decision Process

Small, reversible changes are decided through pull-request review. Changes to
the following surfaces should begin with a public proposal or design document:

- CLI or JSON compatibility
- Relay database schema or migration behavior
- lease compatibility or fencing semantics
- identity, authentication, privacy, or project isolation
- the scope-first enrollment model
- public protocol or deployment boundaries

Maintainers seek rough consensus. When consensus is not possible, T54 Labs as
project steward makes the final decision and records the rationale.

## Release Process

Commons follows semantic versioning for public releases. Before `1.0.0`, minor
releases may contain documented breaking changes. Every release
must pass the repository CI, update `CHANGELOG.md`, and satisfy the maintainer
release checklist.

## Product Boundary

The open-source project includes the CLI, Agent Skill, local filesystem mode,
private Relay, Console, tests, examples, and deployment material.

T54 Labs does not promise a public hosted Commons Relay. One self-hosted Relay
represents one trusted team or organization boundary unless a future design
explicitly introduces stronger multi-tenant isolation.

## AI-Assisted Contributions

AI-assisted work is welcome. The human or organization submitting a change owns
its correctness, licensing, security, and evidence. Material Agent use should be
disclosed in the pull request. Agent output does not receive reduced review, and
an Agent's statement that tests passed is not evidence unless the tests are
independently reproducible.

## Licensing

Unless explicitly stated otherwise, Contributions are licensed under the
Apache License, Version 2.0, as described in `CONTRIBUTING.md`.
