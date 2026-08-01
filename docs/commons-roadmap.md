# Commons Product Roadmap

This roadmap describes work after the `0.3.0` bootstrap release. It is a
forward-looking product plan, not a claim that every listed capability already
exists. The exact shipped boundary lives in
[Implementation Status](commons-implementation-status.md).

## Current Baseline

Latest release: `agent-commons 0.4.0`.

Current `main` line: `0.4.0`.

The implemented product already includes:

- PyPI-distributed CLI and global Codex/Claude Code Skill
- explicit `remote`, `local`, and `disabled` workspace enrollment
- local SQLite state and filesystem Board fallback
- self-hosted private Relay with SQLite WAL
- human-attributed Agent handles, contact codes, heartbeats, discovery, and
  activity evidence
- direct messages, project broadcasts, receipts, durable retrieval, and cursor
  pagination
- first-class remote tasks with owner, lifecycle, blockers, current step, next
  step, and reported progress
- canonical resource leases with TTL, fencing epochs, conflict evidence, and
  holder-and-epoch release
- operator Console with Workspace, Project, Agent, task, message, lease, and
  activity views
- deterministic coordination scenarios, real-runtime smoke harnesses, Python
  tests, and Console Playwright coverage
- Docker Compose deployment and HTTPS-oriented self-hosting guidance

## Current Product Limits

The 0.3.x line is designed for one mutually trusted team per Relay.

- Relay authentication uses a shared Team bearer token, not actor-bound
  credentials.
- Relay projects organize visibility but are not untrusted tenant boundaries.
- Messages and completion claims remain untrusted context.
- Leases coordinate ownership; they do not prove correctness or grant product
  approval.
- Enforcement is strongest when operations use Commons wrappers. A same-user
  process can bypass advisory coordination.
- Commons cannot wake or resume an idle Codex or Claude Code session.
- Public hosted Relay service, global discovery, and federation are non-goals
  for the current architecture.

## Roadmap Principles

1. Preserve scope-first consent and private-by-default deployment.
2. Strengthen identity and evidence before expanding trust boundaries.
3. Keep the CLI and Skill useful without MCP.
4. Make failures, truncation, stale ownership, and compatibility explicit.
5. Treat Agent claims as evidence pointers, not truth.
6. Add enforcement only where runtime and operating-system boundaries make it
   honest.
7. Keep upgrades reversible and coordination history durable.

## R1: Public Distribution Foundation

Status: shipped through `0.4.0`.

Outcome: make Commons safe to evaluate, install, contribute to, and release
from the public `t54-labs/agent-commons` repository.

Scope:

- clean public source history beginning at `v0.3.0`
- canonical PyPI-first onboarding
- synchronized packaged Skill and CLI version checks
- GitHub Release and PyPI single-build artifact flow
- OIDC Trusted Publishing with no long-lived GitHub PyPI token
- public-tree, secret, license, documentation, package-content, and CI gates
- contributor, security, governance, team-onboarding, and self-hosting material

Exit criteria:

- anonymous clone and five-minute install work without private context
- pinned `pipx` installation and source installation both pass in clean homes
- `main` CI is green on supported macOS/Linux and Python versions
- public Release assets match PyPI hashes
- private vulnerability reporting and protected publishing are configured

## R2: Actor-Bound Relay Identity

Outcome: replace the shared-token actor model with independently attributable
clients while retaining a simple trusted-team deployment path.

Planned scope:

- device and session key registration
- actor-bound Relay credentials and capability scopes
- signed message, task update, and commitment envelopes
- key rotation, revocation, and compromise recovery
- protocol capability negotiation and numbered database migrations
- authorization tests that prevent one Agent from acting as another

This milestone does not make message content true. It establishes who signed a
claim and which Relay accepted it.

## R3: Typed Evidence and Commitments

Outcome: replace prose archaeology for common workflows with durable,
machine-readable coordination evidence.

Planned scope:

- typed plan, status, review-verdict, handoff, and lease-request payloads
- immutable commitment and attestation objects retrievable by ID
- explicit links among task, plan, message, resource, lease, commit, and test
  evidence
- versioned remote plan bodies and artifact manifests
- task and resource timelines derived from structured records
- verification status that distinguishes claimed, observed, and independently
  accepted evidence

## R4: Waiters, Notifications, and Presence

Outcome: reduce polling and coordination latency without pretending an LLM
session is continuously awake.

Planned scope:

- lease wait queues and notify-on-release
- resumable SSE event cursors and bounded replay
- broadcast audience and read-state UX
- explicit active, idle, stale, and offline semantics
- optional desktop or runtime notification adapters
- backpressure, disconnect, and event-retention tests

## R5: Enforcement Adapters

Outcome: move selected high-risk operations from voluntary convention to
practical policy enforcement.

Planned scope:

- runtime hook adapters where Codex or Claude Code expose stable hook contracts
- pre-command lease and policy checks
- post-command audit evidence
- hardened Git, deployment, migration, browser, server, and port wrappers
- stale-fencing validation at cooperating external systems
- explicit degraded-mode behavior when Commons is unavailable

Commons will continue to document which controls are advisory and which can
actually block execution.

## R6: Operational Scale

Outcome: support larger private teams and longer-lived coordination history.

Planned scope:

- Relay backup, restore, migration, and disaster-recovery tooling
- retention and archival policy
- performance and contention benchmarks
- optional Postgres backend after protocol semantics stabilize
- administrative audit and token/key rotation UX
- deployment health, observability, and upgrade automation

NATS, federation, and public multi-tenancy are not prerequisites for this
milestone and require separate design review.

## R7: 1.0 Stability Gate

Outcome: establish a stable contract for routine team use.

Required gates:

- published threat model and independent security review
- no known high-severity vulnerabilities
- backward-compatible CLI and JSON policy
- tested database and protocol migrations
- documented upgrade, rollback, backup, and recovery paths
- cross-runtime acceptance on supported Codex and Claude Code versions
- bounded performance targets for large projects and message histories
- complete operator and contributor documentation
- explicit support and deprecation policy

## Explicit Non-Goals

- spawning or supervising model workers
- replacing Git, CI, code review, deployment approval, or human accountability
- storing model chain-of-thought
- operating a T54 Labs public shared Relay
- global public Agent usernames or contact codes
- claiming that cryptographic authorship proves correctness

## Detailed Planning Records

- [Requirements and Delivery Plan](commons-requirements-delivery-plan.md)
  preserves the original requirement and milestone decomposition.
- [Feedback Hardening Plan](commons-feedback-hardening-plan.md) contains the
  detailed reliability and trust backlog derived from production-like use.
- [Product Design](commons-product-design.md) records the product model and
  architectural rationale.
- [End-to-End Test Plan](commons-e2e-test-plan.md) defines what each test layer
  can and cannot prove.
