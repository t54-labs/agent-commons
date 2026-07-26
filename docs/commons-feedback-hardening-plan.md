# Commons Feedback Hardening and Trust Roadmap

> **Document status:** Active detailed backlog derived from real usage. The
> disposition table distinguishes implemented, partial, and planned behavior;
> later milestone sections must not be read as shipped capability.

## Purpose

This plan converts production-like usage feedback into an executable delivery track. It preserves the product decisions that already work and closes the gap between an advisory coordination mailbox and a trustworthy multi-agent control plane.

This document is normative for the feedback hardening track. It defines requirements, test boundaries, milestones, every milestone subtask, and release gates.

## Product Invariants

The following behavior must not regress:

1. Workspace enrollment remains scope-first: `remote`, `local`, `disabled`, or an explicit human decision for `unknown`.
2. A workspace never joins a relay implicitly.
3. Leases retain TTL expiry, compatibility modes, and monotonic fencing epochs.
4. Agent identity retains `agent_id`, `handle`, and `contact_code`.
5. Every automation-facing command provides JSON output.
6. Agents inspect inboxes and active leases before shared work.
7. A self-hosted relay remains a private team trust boundary, not a public global network.

## Feedback Disposition

| Item | Status | Product disposition |
| --- | --- | --- |
| B1 project context on first write | Implemented | Project context is injected in one HTTP layer, duplicated in `X-Commons-Project`, reconciled by the relay, and reported with actionable errors. |
| B2 silent inbox cap | Implemented | Relay pages report the 200-item server cap and completeness; CLI auto-pagination honors larger limits; cursors, `--before`, message lookup by id, and `--items-only` are available. |
| S1 signed messages | Planned in FH2 | Requires a real identity bootstrap and key lifecycle, not a signature field alone. |
| S2 commitments and attestations | Planned in FH3 | Immutable signed records get independent ids, exact-byte retrieval, and relay acceptance receipts. |
| S3 typed payloads | Planned in FH3 | Versioned schemas cover plans, status, review verdicts, lease requests, and summaries. |
| S4 canonical lease resources | Lexical normalization implemented; registry planned in FH4 | Spelling variants collide today. Cross-namespace aliases and repository identities require an explicit registry. |
| S5 lease wait and notify | Planned in FH5 | Durable FIFO waiters and event delivery replace client polling. |
| S6 broadcast receipts and presence | Partially implemented | Per-agent receipts and heartbeat-derived presence exist. Realtime receipt and presence events remain in FH5. |
| S7 error source distinction | Implemented for Commons surfaces | CLI errors identify `commons-client`, `commons-relay`, or `commons-policy`. Runtime approval failures remain outside Commons and must be labeled by the invoking agent. |
| S8 resource and task timelines | Planned in FH4 | The remote audit model must be project-filtered and correlated before exposing timeline APIs. |
| S9 handle suggestions | Implemented | Handle conflicts return stable error codes and available suggestions. |
| S10 first-class remote tasks | Core implemented in 0.3.0 | Remote tasks now expose owner, status, current and next steps, blockers, dependencies, optional reported progress, and optimistic versions. Versioned remote plan bodies and complete task-resource relations remain in FH4. |

## Adversarial Validation Summary

Three independent read-only reviews challenged the implementation from distributed-systems, security, and runtime-UX perspectives. Their blocking findings were converted into FH0.1 code and tests:

- Resource normalization now refuses to merge or invalidate active legacy leases during migration.
- Broadcast audience membership is frozen at send time; senders, late joiners, and arbitrary ids cannot acknowledge historical delivery.
- Inbox cursors use monotonic insertion sequence instead of second-resolution timestamps plus random ids.
- New clients mark legacy bare-array completeness as unknown, while new relays preserve array output for old clients that do not request envelopes.
- Remote messages and leases require registered actors; release requires holder plus fencing epoch and is idempotent.
- Observational leases no longer advance a writer's fencing epoch.
- Remote audit reads are project-filtered.
- Relay initialization and migrations run once per database per process under a lock, rather than on every request.
- Legacy direct and attributable broadcast acknowledgements are migrated to per-agent receipts.
- Presence heartbeat refresh no longer erases explicit `busy` or `idle` workload status.
- Remote status performs an authenticated project probe.
- Skill registration checks command exit status, consumes handle suggestions, carries project context, redacts absolute workspace paths, and retains lease epochs.
- Doctor compares installed Skill hashes instead of treating file existence as current installation.

The reviews also confirmed two boundaries that remain open and must not be overclaimed:

1. The current shared relay token is not actor-bound authentication. Any token holder can still attempt actor spoofing until FH1 session proof-of-possession ships.
2. Current resource normalization is lexical. Semantic repository identity, aliases, and filesystem case policy remain FH4 work.

## Requirements

### Reliability and Compatibility

| ID | Priority | Requirement |
| --- | --- | --- |
| FH-R001 | P0 | Every project-scoped client request must inject one resolved project at the shared HTTP boundary. |
| FH-R002 | P0 | The relay must reject conflicting header, query, and body project values. |
| FH-R003 | P0 | Errors must expose a stable `error_code`, `error_source`, and actionable remediation when one exists. |
| FH-R004 | P0 | Inbox responses must state the requested limit, returned count, server page limit, completeness, and continuation cursor. |
| FH-R005 | P0 | A CLI request larger than one server page must traverse pages until the requested count or archive end. |
| FH-R006 | P0 | A message must remain retrievable by id after it leaves the current inbox window. |
| FH-R007 | P0 | Broadcast acknowledgement state must be independent for every receiving agent. |
| FH-R008 | P0 | Schema and data migrations must be idempotent and preserve existing messages, leases, epochs, and receipts. |
| FH-R009 | P1 | Client and relay must negotiate capabilities before using a response shape or endpoint introduced after the base protocol. |
| FH-R010 | P1 | One release must preserve legacy inbox arrays through `--items-only`; removal requires a documented major-version boundary. |

### Actor Authorization and Project Isolation

| ID | Priority | Requirement |
| --- | --- | --- |
| FH-A001 | P0 | Relay credentials must resolve to allowed project ids and capabilities on the server; a client-supplied project is never an authorization decision. |
| FH-A002 | P0 | Agent registration must prove possession of a session public key and must not overwrite an existing identity without the bound key or an audited recovery flow. |
| FH-A003 | P0 | Every actor operation must use a short-lived session credential plus proof of possession bound to method, path, body digest, nonce, and timestamp. |
| FH-A004 | P0 | The relay must derive sender, inbox reader, acknowledgement actor, heartbeat actor, lease holder, and releaser from the authenticated session. |
| FH-A005 | P0 | Handles, contact codes, `agent_id`, and a shared bootstrap token are routing or enrollment values, never authentication credentials. |
| FH-A006 | P0 | Direct inbox reads, message retrieval, acknowledgements, and lease release must reject a valid project member acting as another agent. |
| FH-A007 | P1 | Bootstrap, agent, operator, and administrator capabilities must use separate, revocable credentials with hashed server-side storage. |
| FH-A008 | P1 | Remote registration must not upload an absolute local workspace path by default. |

### Verifiable Identity and Messages

| ID | Priority | Requirement |
| --- | --- | --- |
| FH-I001 | P0 | Every installation must have a stable device signing identity distinct from an ephemeral agent session. |
| FH-I002 | P0 | Every agent session must have its own signing key certified by the device key. |
| FH-I003 | P0 | A signed message must bind project, message id, sender session, resolved recipient, thread, type, exact body hash, exact payload hash, client timestamp, and nonce. |
| FH-I004 | P0 | Relay verification must reject invalid signatures, altered fields, unknown keys, duplicate message ids, and replayed nonces. |
| FH-I005 | P0 | Clients must independently verify signatures from stored bytes and pinned identity material. |
| FH-I006 | P0 | First-use key binding must be labeled `continuity_tofu` or `unverified_bootstrap`, never trusted identity, unless backed by an administrator-signed project membership manifest. |
| FH-I007 | P0 | A relay token alone must never be described as proof of agent authorship. |
| FH-I008 | P1 | Key rotation must preserve historical verification and require the old device key or an administrator recovery action. |
| FH-I009 | P1 | Revocation must stop new messages while keeping historical signatures verifiable. |
| FH-I010 | P1 | Private keys must use OS-backed secure storage where available and a `0600` file fallback with explicit diagnostics. |

### Commitments and Typed State

| ID | Priority | Requirement |
| --- | --- | --- |
| FH-C001 | P0 | A commitment must be immutable, signed, project-scoped, and retrievable by `commitment_id`. |
| FH-C002 | P0 | A commitment must bind subject, kind, exact payload hash, evidence references, author identity, and client timestamp. |
| FH-C003 | P0 | Relay acceptance must add an immutable server timestamp and a signed receipt without rewriting the author-signed statement. |
| FH-C004 | P0 | Verification must report author signature validity, identity trust state, payload hash validity, and relay receipt validity separately. |
| FH-C005 | P0 | Typed message payloads must carry `schema_id`, `schema_version`, and exact persisted JSON bytes. |
| FH-C006 | P0 | Built-in schemas must cover `plan`, `status`, `review-verdict`, `lease-request`, `context`, and `summary`. |
| FH-C007 | P1 | Unknown schemas must use an organization namespace and remain readable as untrusted custom payloads. |
| FH-C008 | P1 | Schema validation failures must identify the exact field and expected type without discarding the original local file. |

### Resources, Tasks, and Timelines

| ID | Priority | Requirement |
| --- | --- | --- |
| FH-T001 | P0 | Remote resources must use validated canonical ids and store aliases in a project-scoped registry. |
| FH-T002 | P0 | A repository resource identity must derive from a normalized Git remote plus repository-relative path, not an absolute machine path. |
| FH-T003 | P0 | Remote tasks must expose owner, status, summary, blocked-by edges, related resources, and current plan version. |
| FH-T004 | P0 | Task ownership changes and status transitions must be transactional and audited. |
| FH-T005 | P0 | Timeline queries must be project-scoped and filter by task, resource, agent, thread, or commitment. |
| FH-T006 | P1 | A timeline must correlate plan, message, lease, commit, test, review, release, and acknowledgement events without parsing prose. |
| FH-T007 | P1 | Timeline pagination must be cursor-based and stable under concurrent writes. |

### Wait, Notify, and Presence

| ID | Priority | Requirement |
| --- | --- | --- |
| FH-W001 | P0 | A denied lease may create a durable waiter with timeout, requested mode, reason, and agent id. |
| FH-W002 | P0 | Waiter ordering must be deterministic and starvation-resistant for incompatible modes. |
| FH-W003 | P0 | Release and expiry must wake eligible waiters, but a waiter must still win a new transactional acquire and fencing epoch before acting. |
| FH-W004 | P0 | Disconnecting a client must not silently grant a lease that no client can observe. |
| FH-W005 | P1 | SSE must deliver message, receipt, presence, lease, task, and commitment events with replay from the last event id. |
| FH-W006 | P1 | Presence must distinguish observed heartbeat state from an authoritative guarantee that an agent is currently executing. |
| FH-W007 | P1 | Broadcast receipt summaries must identify the stable audience snapshot used for `all_acked`. |

## Trust Architecture

### Identity Layers

Commons needs four distinct identities:

1. Project trust root: an administrator-controlled public key or signed membership manifest.
2. Device identity: one stable Ed25519 key per Commons installation.
3. Agent session identity: one ephemeral Ed25519 key per Codex or Claude Code session.
4. Human address: the existing handle and contact code, mapped to the session identity.

The device key signs a short-lived session certificate. Messages and commitments are signed by the session key. A receiver verifies the session signature, the device certificate, and the device trust state independently.

A shared bearer token may remain only as a migration-time bootstrap and rate-limit barrier. It is not authorship evidence or project isolation. FH1 replaces actor-controlled request fields with server-derived project and actor context. Each request then carries a short-lived session credential plus a proof-of-possession signature over the HTTP method, path, body digest, timestamp, and nonce.

The relay must reject a request when the authenticated project or actor differs from any redundant value in the payload. A handle, contact code, or `agent_id` remains a routing alias, not a credential.

### First Trust Decision

Two modes are required:

- TOFU continuity: the first observed device fingerprint is pinned locally. Verification reports `continuity_tofu`, not trusted identity, and any key change is a blocking warning.
- Managed membership: an administrator-signed manifest binds a device public key to a project member. Verification reports `trusted_managed`.

The product must not display either mode as global identity. Trust remains scoped to one self-hosted relay project.

### Signed Envelope

Commons uses DSSE pre-authentication encoding for domain separation and Ed25519 signatures. The DSSE payload type is `application/vnd.commons.message.v1+json`. The payload is strict I-JSON serialized with an audited RFC 8785 implementation; duplicate keys, non-finite numbers, and schema-disallowed floating point values are rejected. The relay stores the exact payload and signature bytes and never recreates signed bytes from parsed JSON.

Version 1 binds:

```text
domain = "commons.message.v1"
project_uid
message_id
sender_agent_id
session_key_id
recipient_agent_id or "*"
thread_id
message_type
schema_id
body_sha256
payload_sha256
client_created_at
nonce
session_sequence
session_certificate_sha256
```

Direct messages resolve a handle or contact code to `recipient_agent_id` before signing. The relay rejects a request if its routing result differs from the signed recipient.

The relay enforces uniqueness for `message_id` and `(project_uid, session_key_id, session_sequence)`. An exact retry returns the original result; reuse with different bytes is a replay conflict. Cross-project replay fails because `project_uid` is signed.

The relay stores `accepted_at` separately. A sender signature proves authorship of the signed client timestamp; it does not prove wall-clock truth. Strong timestamp claims require a later external transparency anchor.

### Key Storage and Crypto Dependency

Commons should use the audited `cryptography` Ed25519 implementation. A core security feature should not use handwritten crypto or shell out to platform-specific `ssh-keygen` behavior.

The dependency is accepted for clients that enable signed coordination. During one compatibility release it may be an install extra, but signed messages become mandatory before the trust feature is declared stable.

### Commitments

A commitment is not an inbox message. It is a DSSE-wrapped in-toto Statement with an immutable id and retention policy. The statement subject contains Git, artifact, task, lease, or resource digests. Its predicate type identifies `test-result/v1`, `review-verdict/v1`, `commitment/v1`, or another versioned schema. Corrections, revocations, and superseding claims create new signed statements instead of mutating old ones.

The persisted record contains:

```text
commitment_id
project_id
author_agent_id
kind
subject
schema_id
schema_version
payload_bytes
payload_sha256
evidence_refs
client_created_at
signature
signing_key_id
accepted_at
relay_receipt_signature
relay_receipt_key_id
```

Suggested commands:

```bash
commons remote commitment create --kind test-result --subject git:<sha> --payload result.json --agent <agent_id>
commons remote commitment get <commitment_id> --agent <agent_id>
commons remote commitment verify <commitment_id> --agent <agent_id>
commons remote commitment list --subject git:<sha> --kind review-verdict
```

The relay receipt key is certified by the project trust root. Its signature proves only the relay's statement that it accepted an object with a specific digest, sequence, and server timestamp. It does not prove objective wall-clock time. A bare receipt hash is only a checksum and must not be presented as authentication.

Verification returns separate booleans and trust labels. It must never collapse an untrusted key, valid signature, and valid relay receipt into one `verified: true` field. The minimum result surface is:

```text
signature: valid | invalid | unsigned
identity: trusted_managed | continuity_tofu | unknown | revoked
revocation: current at <epoch> | stale | unknown
payload_integrity: valid | invalid
relay_receipt: valid | invalid | absent
relay_time: relay_asserted | absent
evidence: evaluated | not_evaluated
claim_truth: not_proven
```

## Test Boundaries

### Automated Coverage

The release suite must cover:

- project context omission, mismatch, and default injection on every write endpoint
- old and new relay capability negotiation
- 0, 1, 199, 200, 201, 500, and 5,000-message inbox windows
- cursor traversal while concurrent messages are appended
- `--before` and message-id retrieval after window eviction
- per-agent direct and broadcast acknowledgements
- legacy message receipt migration
- resource spelling variants, invalid traversal, aliases, and migration collisions
- concurrent incompatible lease acquisition with one winner
- waiter timeout, cancellation, release wakeup, expiry wakeup, fairness, and fencing epoch freshness
- Ed25519 known-answer vectors and altered-field rejection
- key substitution, unknown device, revoked device, rotated key, replayed nonce, and duplicate id rejection
- shared-token impersonation, cross-project reads, actor-field substitution, and session proof replay
- JSON duplicate keys, Unicode normalization boundaries, non-finite numbers, and cross-language DSSE fixtures
- exact payload-byte and body-hash verification
- commitment retrieval and verification after inbox truncation
- typed schema validation and unknown custom schema behavior
- task ownership races, dependency cycles, and timeline pagination
- SSE disconnect, replay, duplicate delivery, and stale cursor recovery
- upgrade from every supported relay schema version with real fixture databases
- fresh Codex and Claude Code sessions using the installed global Skill

### Manual and Multi-Host Coverage

Manual release gates must include:

1. One Codex and one Claude Code session on the same machine.
2. One Codex and one Claude Code session on different machines through one private relay.
3. A relay restart while messages, waiters, and unacknowledged events exist.
4. An agent crash after lease expiry, followed by a new holder with a higher fencing epoch.
5. A key-change warning that blocks trust until a human confirms rotation or managed membership.
6. A signed test-result commitment independently verified on another machine.

### Explicit Non-Claims

Tests do not claim that Commons can:

- prevent a process from bypassing Commons and writing directly to an external service
- prove that a test command really ran solely because an agent signed a statement
- establish true wall-clock time without an external timestamp or transparency service
- protect private keys on a fully compromised host
- isolate hostile agents running as the same operating-system user without a separate signing service, container, or OS account
- prevent a trusted project administrator from changing membership policy
- keep message bodies, activity metadata, or Git references secret from the private relay operator without a future end-to-end encryption mode
- wake a terminated Codex or Claude Code session unless the runtime exposes a supported wakeup mechanism
- provide global identity or cross-organization trust

## Milestones and Subtasks

### FH0: Immediate Reliability Patch

Status: implemented in version 0.2.0.

Subtasks:

- Centralize project context injection.
- Add redundant project headers and relay reconciliation.
- Add stable error sources, codes, and remediation.
- Add explicit inbox page metadata.
- Add cursor and `--before` pagination.
- Add CLI auto-pagination for large limits.
- Add durable message lookup by id.
- Migrate acknowledgements to per-agent receipts.
- Add lexical resource canonicalization and validation.
- Add presence and heartbeat endpoints.
- Add handle conflict suggestions.
- Freeze broadcast audience snapshots.
- Replace timestamp cursors with monotonic message sequence cursors.
- Preserve old-client array responses and mark old-relay completeness unknown.
- Require registered remote senders and lease holders.
- Require holder and fencing epoch on remote release.
- Make repeated release idempotent.
- Advance fencing epochs only for fencing-capable lease modes.
- Block unsafe canonical-resource migrations with active leases.
- Scope remote audit reads to a project.
- Run relay migrations once per database per process.
- Authenticate remote status probes.
- Detect stale installed Skills by content hash.
- Update Skill and CLI documentation.

Release gate:

- Full unit and local relay E2E suites pass.
- Existing databases migrate idempotently.
- Legacy inbox consumers have `--items-only`.
- Old clients receive arrays from new relays, and new clients never claim a legacy array is a complete archive.
- Active resource migration collisions stop startup instead of creating two valid exclusive leases.

Deployment order for 0.2.0 is intentionally client-first because fenced release is a security contract change:

1. Upgrade the CLI and global Skills on every active workstation.
2. Wait for or explicitly release all leases created by older clients.
3. Back up the relay database and verify the backup can be opened.
4. Upgrade and restart the relay.
5. Run authenticated status, inbox, message, canonical-resource conflict, and fenced-release smoke tests.

Server-first deployment is unsupported for 0.2.0. FH1 capability negotiation and numbered migrations remove this ordering constraint for later releases.

### FH1: Protocol Compatibility, Actor Auth, and Project Isolation

Goal: make independent upgrades safe and stop a shared relay token from impersonating agents or crossing project boundaries.

Subtasks:

- Add `GET /v1/capabilities` with protocol and schema versions.
- Add CLI capability cache scoped by remote URL and token identity.
- Define minimum and maximum supported protocol versions.
- Reject unsupported response shapes with remediation instead of Python type errors.
- Add numbered SQLite relay migrations and a migration ledger.
- Add backup-before-migration and restore verification.
- Add fixture databases for every released schema.
- Add client fallback for legacy bare inbox arrays.
- Add deprecation telemetry that contains no message bodies or private identifiers.
- Document rolling upgrade and rollback order.
- Add project-scoped credential records with hashed token storage and capabilities.
- Split bootstrap, agent, operator, and administrator credentials.
- Add one-time registration challenges and session-key proof of possession.
- Add short-lived session credentials and per-request proof signatures.
- Derive project and actor from authenticated server context for every endpoint.
- Remove authorization dependence on request `sender_agent_id`, `agent_id`, and `holder_agent_id` fields.
- Prevent registration overwrite without the bound session or device key.
- Redact absolute workspace paths by default and add an explicit operator opt-in.
- Add audit events for credential issuance, expiry, revocation, and failed actor substitution.

Release gate:

- New client works with the previous relay release.
- New relay works with the previous client release.
- Failed migration restores the original database byte-for-byte.
- A caller holding only the legacy shared token cannot read or acknowledge another agent's direct inbox, send as that agent, heartbeat as that agent, or release its lease.
- A credential issued for one project cannot select another project in a header, query, or body.

### FH2: Signed Device and Session Identity

Goal: make message authorship independently verifiable.

Subtasks:

- Add the audited Ed25519 dependency and known-answer tests.
- Implement device key generation, secure storage, fingerprinting, and export.
- Implement session key generation and device-signed session certificates.
- Add TOFU continuity pin storage and key-change blocking behavior.
- Add administrator-signed project membership manifests.
- Add recipient resolution before message signing.
- Implement DSSE PAE, strict I-JSON, and audited RFC 8785 serialization.
- Add client-generated message ids and nonces.
- Add relay signature verification, idempotency, session sequence, and replay tables.
- Persist signature, key id, certificate chain, and exact signed field hashes.
- Add `remote msg verify` with separate signature and trust results.
- Add key rotation, revocation, and historical verification.
- Update the Skill to treat unsigned messages as unverified legacy context.

Release gate:

- A second machine verifies a message without trusting the relay to assert its author.
- Body, payload, recipient, sender, project, timestamp, and nonce mutation all fail verification.
- Initial TOFU continuity and managed membership are visibly distinct.

### FH3: Commitments and Typed Coordination Payloads

Goal: replace prose conventions and ad hoc hash messages with durable objects.

Subtasks:

- Add immutable DSSE/in-toto attestation storage and relay APIs.
- Add create, get, list, and verify CLI commands.
- Add project-certified relay receipt signatures and acceptance timestamps.
- Add evidence references for Git commits, test artifacts, leases, tasks, and messages.
- Add schema metadata and exact payload-byte storage to messages.
- Publish built-in schemas for plan, status, review verdict, lease request, context, and summary.
- Validate built-in schemas on both client and relay.
- Add organization-namespaced custom schemas.
- Add typed CLI helpers for common payloads.
- Add commitment retention, export, backup, and tombstone policy.
- Add a migration utility that converts recognizable legacy prefixes into typed views without rewriting original messages.

Release gate:

- `tests passed at SHA X` can be represented as a signed commitment and retrieved by id after inbox rollover.
- Review verdict counts are machine-readable without regular expressions.
- Original signed bytes remain unchanged through export and restore.

### FH4: Remote Resources, Tasks, and Timelines

Goal: make ownership and work state first-class on the relay.

Subtasks:

- Add a project-scoped remote resource registry.
- Add canonical Git repository identities and repository-relative path ids.
- Add explicit aliases and alias collision checks.
- Add remote tasks with owner, status, summary, and timestamps.
- Add blocked-by edges with cycle detection.
- Add versioned remote plans and current-plan pointers.
- Add task-resource, message-task, lease-task, and commitment-task relations.
- Make every remote audit query require a project.
- Add task, resource, agent, thread, and commitment timeline filters.
- Add stable cursor pagination for timelines.
- Add Markdown and JSON timeline exports.
- Update the Skill to publish and update remote tasks instead of encoding ownership only in plan prose.

Release gate:

- A human can reconstruct plan to lease to commit to review to release from one task timeline.
- Two agents cannot claim one exclusive task owner in the same transition.
- Equivalent resource aliases cannot bypass a lease.

### FH5: Lease Waiters and Realtime Events

Goal: remove coordination polling while preserving transactional lease safety.

Subtasks:

- Add durable lease waiter records.
- Define FIFO ordering with an explicit policy for read and write starvation.
- Add waiter timeout and cancellation.
- Add transactional promotion attempts after release and expiry.
- Require a new fencing epoch on every promoted acquisition.
- Add `remote lease acquire --wait` and `remote lease wait cancel`.
- Add durable relay event ids.
- Add SSE with last-event-id replay.
- Emit message, receipt, presence, lease, task, and commitment events.
- Add reconnect backoff and duplicate suppression in the CLI.
- Add optional desktop, webhook, and shell notification adapters.
- Define behavior when a runtime cannot wake a stopped agent.

Release gate:

- A waiting agent receives and validates a lease without manually polling.
- Relay restart does not lose waiters or replayable events.
- No agent acts on a notification without a granted lease and current fencing epoch.

### FH6: Cross-Runtime Hardening Release

Goal: prove the complete product experience with Codex and Claude Code.

Subtasks:

- Add a real remote-mode runtime harness rather than local-board-only prompts.
- Add two-machine fixtures with isolated Commons homes.
- Add signed plan, commitment, and review-verdict scenarios.
- Add 500-plus-message rollover and archive verification.
- Add canonical resource spelling contention scenarios.
- Add lease waiter handoff and relay restart scenarios.
- Add key rotation and revocation scenarios.
- Add prompt-injection messages inside typed payloads.
- Add upgrade and rollback tests against copied production-shaped databases.
- Add performance tests for 100,000 messages, 10,000 commitments, and 1,000 active agents.
- Add threat-model review and independent security review.
- Publish release notes, operator runbook, backup guide, and compatibility matrix.

Release gate:

- All automated, manual, and multi-host gates pass.
- No known P0 or P1 correctness or security findings remain open.
- A fresh team can deploy a relay, install the Skill, enroll selected workspaces, and complete the full signed coordination flow from documentation alone.

## Delivery Order

The required order is FH1, FH2, FH3, FH4, FH5, then FH6.

Signed commitments must not ship before protocol negotiation and migrations. Timelines must not ship before typed relations. Lease notifications must not ship before durable event replay. This ordering avoids building user-visible guarantees on response contracts or identity assumptions that are still unstable.
