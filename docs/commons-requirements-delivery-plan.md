# Commons Requirements, Test Boundaries, and Delivery Plan

> **Document status:** Original full delivery record. It preserves requirement
> IDs, test boundaries, milestones, and subtasks used to build Commons. It is
> not the current sprint plan. Use
> [Implementation Status](commons-implementation-status.md) for shipped
> behavior and [Roadmap](commons-roadmap.md) for forward priorities.

## Document Purpose

This is the detailed historical planning document for Commons. It defines:

1. Product requirements.
2. Test boundaries and what each test layer can prove.
3. Development milestones.
4. The full subtask breakdown for each milestone.

Commons is intended to become a complete, usable product. The milestones are implementation phases, not a claim that the first phase is the final product.

## Product Definition

Commons is a local-first coordination control plane for coding agents. It helps Codex, Claude Code, and other agent runtimes discover each other, publish plans, exchange scoped context, coordinate shared resources, and produce an auditable record of work.

Commons is not only a mailbox or BBS. Its core responsibility is coordination around external side effects:

- staging environments
- databases
- deployment slots
- git branches
- browser profiles
- local ports
- long-running servers
- cloud resources
- shared credentials and tool access

## Product Capability Levels

Commons must clearly distinguish what level of safety is active.

### Level 0: Visibility

Agents can register, publish tasks, publish plans, send messages, and inspect status. This improves awareness but does not block risky operations.

Required components:

- `commonsd`
- `commons` CLI
- task, plan, message, and audit state
- agent presence

### Level 1: Advisory Coordination

Agents use the Commons Skill, the `commons` CLI, and the filesystem board. They are instructed to coordinate before acting, but the runtime may still bypass Commons.

Required components:

- Level 0
- Commons Skill
- filesystem board
- setup doctor

### Level 2: Enforced Local Coordination

High-risk operations go through Commons wrappers or blocking hooks. Commons can block configured commands before execution.

Required components:

- Level 1
- resource leases
- policy gate
- `commons run`
- high-risk operation wrappers
- blocking hooks where the runtime supports them

### Level 3: Team Coordination

Multiple machines coordinate through a shared backend with stronger identity, authorization, and audit controls.

Required components:

- Level 2
- Postgres backend
- authenticated multi-user access
- per-resource authorization
- team policy
- durable event fanout

Level 3 is not a Local Mode guarantee.

## Requirements

### Requirement Categories

Priority values:

- `P0`: required for the first usable local product.
- `P1`: required before private beta.
- `P2`: required before public beta.
- `P3`: required before GA or team mode.

Verification values:

- `simulator`: deterministic tests with fake agents.
- `cli`: real CLI/daemon integration tests.
- `fake-resource`: wrapper tests against fake staging, fake DB, fake git, fake browser, or fake server resources.
- `runtime`: real Codex or Claude Code acceptance tests.
- `manual`: manual acceptance or security review.

### Functional Requirements

| ID | Priority | Requirement | Verification |
| --- | --- | --- | --- |
| FR-001 | P0 | Commons core coordination must work through the `commons` CLI, SQLite WAL, and filesystem board without requiring MCP or a daemon. | cli |
| FR-002 | P0 | Commons must provide a scriptable CLI named `commons`. | cli |
| FR-003 | P0 | Agents must be able to register a session with runtime, workspace, repo, branch, host, pid, and status metadata. | simulator, cli |
| FR-004 | P0 | Agents must be able to heartbeat and become stale when heartbeats stop. | simulator, cli |
| FR-005 | P0 | Agents must be able to list active agents. | simulator, cli |
| FR-006 | P0 | Agents must be able to create, claim, update, block, complete, fail, and cancel tasks. | simulator, cli |
| FR-007 | P0 | Agents must be able to publish versioned plans with current step, next steps, expected resources, blockers, and validation steps. | simulator, cli |
| FR-008 | P0 | Agents must be able to send, read, reply to, and acknowledge threaded messages. | simulator, cli |
| FR-009 | P0 | Commons must write append-only audit events for every state mutation. | simulator, cli |
| FR-010 | P0 | Commons must expose `commons status` with a human-readable view of active agents, tasks, leases, conflicts, unread messages, and stale sessions. | cli |
| FR-011 | P0 | Commons must expose `commons status --json` for agents and automation. | cli |
| FR-012 | P0 | Commons must provide `commons init`, `commons up`, and `commons doctor`. | cli |
| FR-013 | P1 | Commons must provide `commons doctor --fix` for safe automatic setup repairs. | cli, manual |
| FR-014 | P1 | Commons must support direct and task-scoped messages between agents. | simulator, cli, runtime |
| FR-015 | P1 | Commons must support scoped context packets without requiring full transcript sharing. | simulator, cli, runtime |
| FR-016 | P1 | Commons must support artifact attachment with type, visibility, checksum, and task association. | simulator, cli |
| FR-017 | P1 | Commons must provide Markdown task and resource exports. | cli |
| FR-018 | P2 | Commons must provide optional `commonsd`, `commons watch`, and `commons status --watch` for realtime-ish observation. | cli |
| FR-019 | P2 | Commons must provide a TUI if watch/status output is insufficient for daily use. | manual |
| FR-020 | P3 | Commons must provide optional Web UI for observability and approvals. | manual |

### Resource Lease Requirements

| ID | Priority | Requirement | Verification |
| --- | --- | --- | --- |
| LR-001 | P0 | Commons must model resources with canonical ids. | simulator, cli |
| LR-002 | P0 | Commons must support resource aliases so equivalent resource names cannot bypass leases. | simulator, cli |
| LR-003 | P0 | Commons must support lease modes: `observe`, `read`, `write`, `exclusive`, `maintenance`. | simulator, cli |
| LR-004 | P0 | Commons must enforce a deterministic compatibility matrix for lease modes. | simulator, cli |
| LR-005 | P0 | Commons must use database transactions for lease acquisition. | simulator, cli |
| LR-006 | P0 | Commons must deny conflicting active leases before operation execution. | simulator, cli, fake-resource |
| LR-007 | P0 | Commons must use a per-resource monotonically increasing `fencing_epoch`, not only random tokens. | simulator, cli |
| LR-008 | P0 | Renew, release, and force-release must verify lease id, holder, state, and fencing epoch. | simulator, cli |
| LR-009 | P0 | Expired leases must remain visible in audit history. | simulator, cli |
| LR-010 | P0 | Stale agent recovery must create audit events and must not silently delete leases. | simulator, cli |
| LR-011 | P1 | Commons must support explicit resource hierarchy and policy groups, such as `env`, `db`, and `deploy-slot` relationships. | simulator, cli |
| LR-012 | P1 | Commons must produce standard denial/remediation output for lease conflicts. | cli, fake-resource |
| LR-013 | P1 | Long-running wrappers must re-check lease validity at configured checkpoints. | fake-resource |
| LR-014 | P2 | Commons must support human-approved force recovery flows. | cli, manual |
| LR-015 | P3 | Team Mode must support multi-host lease coordination through Postgres transactions. | cli, manual |

### Policy and Wrapper Requirements

| ID | Priority | Requirement | Verification |
| --- | --- | --- | --- |
| PR-001 | P0 | `commons run` must acquire or validate a lease before executing a configured high-risk operation. | cli, fake-resource |
| PR-002 | P0 | `commons run` must record `operation.started` and `operation.completed` or `operation.failed`. | cli, fake-resource |
| PR-003 | P0 | If policy denies an operation, the wrapped command must not execute. | fake-resource |
| PR-004 | P0 | Policy denial output must include resource, holder, expiry, reason, and safe next actions. | cli, fake-resource |
| PR-005 | P1 | Commons must provide specialized wrappers for deploy, database migration, git push, browser claim, and server restart. | fake-resource |
| PR-006 | P1 | Project policy must configure high-risk command patterns. | cli, fake-resource |
| PR-007 | P1 | Runtime hooks must call Commons policy checks before risky commands where the runtime supports hooks. | runtime, manual |
| PR-008 | P1 | Non-blocking runtimes must emit warnings and audit events rather than claiming enforcement. | runtime |
| PR-009 | P2 | Commons must support approval-required operations such as force release or policy override. | cli, manual |
| PR-010 | P3 | Team Mode must support server-side capability authorization by principal, resource, workspace, and risk level. | manual |

### Agent Runtime Integration Requirements

| ID | Priority | Requirement | Verification |
| --- | --- | --- | --- |
| AR-001 | P0 | Commons must provide a universal Skill source with runtime-specific installation adapters. | cli, runtime |
| AR-002 | P0 | Codex installation must be checkable by `commons doctor`. | cli, runtime |
| AR-003 | P0 | Claude Code installation must be checkable by `commons doctor`. | cli, runtime |
| AR-004 | P1 | Commons must expose a filesystem board with agents, tasks, plans, messages, inboxes, leases, status, and audit exports. | cli, runtime |
| AR-005 | P1 | Agents must be able to register and exchange messages through the CLI and filesystem board. | runtime |
| AR-006 | P1 | Agents must be able to publish plans through the CLI and filesystem board. | runtime |
| AR-007 | P1 | Agents must be able to acquire or be denied leases through CLI commands that update the filesystem board. | runtime |
| AR-008 | P1 | Commons must document that realtime event streams do not guarantee LLM wakeup. | manual |
| AR-009 | P2 | Commons may provide a sidecar that consumes realtime events and notifies or resumes runtime sessions where supported. | runtime, manual |
| AR-010 | P2 | Runtime adapters must be covered by contract tests. | runtime |

### Security and Privacy Requirements

| ID | Priority | Requirement | Verification |
| --- | --- | --- | --- |
| SR-001 | P0 | Documentation must state that Local Mode prevents coordination mistakes, not malicious same-user processes. | manual |
| SR-002 | P0 | If local daemon transport is enabled, it must prefer Unix domain sockets or protected local state paths with `0700` directory permissions. | cli |
| SR-003 | P0 | If localhost HTTP is enabled, it must require a high-entropy token and origin/host checks. | cli |
| SR-004 | P0 | Messages and context packets must be marked as untrusted data in CLI, filesystem board, and UI surfaces. | cli, runtime |
| SR-005 | P0 | Agent messages must not be converted into executable instructions by Commons. | simulator, runtime |
| SR-006 | P1 | Tokens and fencing epochs must not be written to audit exports, messages, artifacts, or normal logs. | cli |
| SR-007 | P1 | Capabilities must be granted by server-side policy, not self-declared by agents. | simulator, cli |
| SR-008 | P1 | Artifact attach must canonicalize paths, reject traversal, avoid symlink surprises, and copy immutable snapshots. | cli |
| SR-009 | P1 | Secret scanning and redaction must run before persistence and indexing. | cli |
| SR-010 | P1 | Secret-risk artifacts must default to `human-only` visibility. | cli |
| SR-011 | P1 | Audit events must be tamper-evident with a hash chain in Local Mode. | cli |
| SR-012 | P2 | Prompt injection tests must verify that malicious agent messages do not trigger command execution. | fake-resource, runtime |
| SR-013 | P3 | Team Mode must include authentication, authorization, revocation, TLS, artifact ACLs, and admin audit. | manual |

### Realtime and Event Requirements

| ID | Priority | Requirement | Verification |
| --- | --- | --- | --- |
| ER-001 | P0 | Durable state must be the source of truth. | simulator, cli |
| ER-002 | P0 | Every mutation must write an audit event and an event outbox row in the same transaction. | simulator, cli |
| ER-003 | P0 | Events must have a globally increasing `event_id`. | simulator, cli |
| ER-004 | P1 | SSE/WebSocket must support replay from `Last-Event-ID` or equivalent cursor. | cli |
| ER-005 | P1 | Event delivery must be at-least-once, and clients must de-duplicate by event id. | cli |
| ER-006 | P1 | Realtime channels must not be the authoritative state. | cli |
| ER-007 | P2 | `commons watch` must show live tasks, messages, leases, and conflicts. | cli |
| ER-008 | P3 | Team Mode may add NATS JetStream or Redis Streams, but durable DB state remains authoritative. | manual |

### Developer Experience Requirements

| ID | Priority | Requirement | Verification |
| --- | --- | --- | --- |
| DX-001 | P0 | A clean local machine must be able to reach the golden path within 10 minutes after installation. | manual |
| DX-002 | P0 | `commons init` must create or validate local configuration. | cli |
| DX-003 | P0 | `commons up` must start the daemon and show setup status. | cli |
| DX-004 | P0 | `commons status` must be useful to humans without extra flags. | cli, manual |
| DX-005 | P0 | All mutating commands must support `--json`. | cli |
| DX-006 | P1 | `commons doctor --fix` must repair safe setup issues. | cli, manual |
| DX-007 | P1 | Common denial outputs must include copy-pasteable safe next commands. | cli |
| DX-008 | P2 | Failure artifacts from E2E must be easy to inspect. | cli, manual |

## Test Boundaries

### Core Rule

No single test layer proves the whole product. Each layer has a defined proof boundary.

### Deterministic Simulator Boundary

Simulator tests prove:

- state machine correctness
- lease compatibility
- stale lease recovery
- audit ordering
- event outbox behavior
- retry idempotency
- policy decisions

Simulator tests do not prove:

- real CLI packaging works
- real Codex or Claude Code follows the skill
- hooks can block runtime commands
- the developer experience is usable

### CLI Integration Boundary

CLI tests prove:

- `commons` and `commonsd` command contracts
- SQLite WAL behavior
- daemon restart recovery
- JSON output schemas
- event replay
- wrapper execution and denial
- export output

CLI tests do not prove:

- LLM agents will choose the right commands
- Claude Code and Codex configs are installed correctly
- real staging or DB resources are safe

### Fake Resource Boundary

Fake resource tests prove:

- risky commands are not executed after policy denial
- fake deploy, fake migration, fake git push, fake browser claim, and fake server restart are gated
- audit events match actual wrapper side effects

Fake resource tests do not prove:

- real cloud providers enforce Commons leases
- real database credentials cannot be used outside Commons
- browser automation cannot be bypassed by another process

### Runtime Acceptance Boundary

Runtime tests with Codex and Claude Code prove:

- the Skill can be installed
- CLI commands and filesystem board files are reachable
- agents can register
- agents can discover each other
- agents can exchange messages
- agents can publish plans
- agents can request and receive lease decisions

Runtime tests do not prove:

- all future prompts will follow the skill
- an idle agent can be woken up by realtime events
- security against malicious same-user processes
- safety when an agent bypasses wrappers and hooks

### Manual Acceptance Boundary

Manual tests prove:

- the workflow feels usable
- status output is understandable
- denial/remediation output is clear
- install and setup instructions work for a real user
- high-risk real environment runs can be supervised safely

Manual tests do not replace:

- simulator tests
- CLI contract tests
- fake resource enforcement tests

### Real Environment Boundary

Real staging, real DB, real cloud, and protected branch tests must be gated. They are not part of ordinary PR CI.

Real environment tests require:

- explicit human approval
- test resource declaration
- backup or rollback plan
- audit export
- post-run cleanup

### CI Boundary

PR CI must run:

- simulator tests
- CLI integration tests
- fake resource tests
- audit/export tests
- redaction tests

Nightly or self-hosted CI may run:

- real Codex smoke tests
- real Claude Code smoke tests
- runtime adapter tests

Manual release gates may run:

- real staging deploy contention
- real DB migration handoff
- real protected branch push policy
- browser profile takeover acceptance

## Golden Path

The first complete product path must be:

1. Install Commons.
2. Run `commons init`.
3. Run `commons up`.
4. Install the Commons Skill for Codex and Claude Code.
5. Start one Codex session and one Claude Code session in the same project.
6. Both agents register.
7. Both agents appear in `commons status`.
8. Agent A publishes a task and plan.
9. Agent B discovers Agent A.
10. Agent B sends Agent A a message.
11. Agent A reads and replies.
12. Agent A acquires `env:fixture/staging`.
13. Agent B requests the same resource in a conflicting mode.
14. Commons denies Agent B before any wrapped command executes.
15. Denial output names the holder, reason, expiry, and safe next actions.
16. `commons audit resource env:fixture/staging` reconstructs the interaction.

This path is the first product proof. It must pass before broader feature expansion.

## Milestones and Subtasks

### Milestone 0: Product Contract and Feasibility

Goal: lock the product boundary and prevent false safety claims.

#### Subtasks

- Write product definition.
- Write explicit non-goals.
- Write capability levels.
- Write threat model for Local Mode.
- Draft an initial Team Mode threat model covering identity, authorization,
  project isolation, message trust, lease bypass, and credential rotation.
- Document that Skill-only coordination is advisory.
- Document that realtime streams do not guarantee agent wakeup.
- Document that wrappers/hooks are required for enforced local coordination.
- Define golden path.
- Define release gates.
- Capture open-source landscape and alternatives.

#### Exit Criteria

- Requirements are written.
- Test boundaries are written.
- Milestone plan is written.
- No document claims strong safety for bypassed wrappers or malicious same-user processes.

### Milestone 1: Local Setup and CLI Skeleton

Goal: make Commons installable and usable on a clean local machine with no daemon or MCP requirement.

#### Subtasks

- Choose implementation language and packaging format.
- Create `commons` CLI entrypoint.
- Create optional `commonsd` daemon entrypoint for status/event streaming.
- Implement `commons version`.
- Implement `commons init`.
- Implement `commons up` as convenience setup.
- Implement optional `commons daemon start`.
- Implement optional `commons daemon stop`.
- Implement optional `commons daemon status`.
- Implement `commons doctor`.
- Implement `commons doctor --json`.
- Add config discovery for `~/.commons/config.toml`.
- Add project config discovery for `.commons/project.toml`.
- Create default state directory with safe permissions.
- Keep CLI plus filesystem board as the default transport.
- Prefer Unix domain socket for optional local daemon transport.
- Add localhost HTTP only behind explicit config and token.
- Add structured logging.
- Add baseline CLI JSON output conventions.
- Add test harness for temp HOME, filesystem board, and optional temp daemon.

#### Exit Criteria

- `commons init && commons doctor` works on a clean local checkout.
- CLI can locate config, SQLite state, and filesystem board.
- Optional daemon can start and stop reliably when enabled.
- Setup failures produce actionable messages.

### Milestone 2: Durable Local State

Goal: implement the state model required for agent coordination.

#### Subtasks

- Add SQLite schema migration system.
- Enable WAL.
- Enable foreign keys.
- Configure busy timeout.
- Create `agents` table.
- Create `tasks` table.
- Create `plans` table.
- Create `messages` table.
- Create `message_threads` table.
- Create `resources` table.
- Create `leases` table.
- Create `operations` table.
- Create `artifacts` table.
- Create `audit_events` table.
- Create `event_outbox` table.
- Add global monotonically increasing `event_id`.
- Add client request id table or uniqueness strategy.
- Implement append-only audit write path.
- Implement event outbox write path.
- Add hash-chain fields for audit events.
- Add DB inspection command for doctor/debug.

#### Exit Criteria

- Mutating commands write audit and outbox records in the same transaction.
- Duplicate client request ids are idempotent.
- Daemon restart preserves all state.
- Simulator tests cover state creation and restart.

### Milestone 3: Agent, Task, Message, and Plan Flows

Goal: deliver Level 0 Visibility.

#### Subtasks

- Implement `commons agent register`.
- Implement `commons agent heartbeat`.
- Implement `commons agent unregister`.
- Implement stale agent detection.
- Implement `commons agent list`.
- Implement `commons agent show`.
- Implement `commons task create`.
- Implement `commons task claim`.
- Implement `commons task update`.
- Implement `commons task block`.
- Implement `commons task complete`.
- Implement `commons task fail`.
- Implement `commons task cancel`.
- Implement `commons plan publish`.
- Implement plan versioning.
- Implement `commons plan show`.
- Implement `commons plan diff`.
- Implement `commons msg send`.
- Implement `commons msg inbox`.
- Implement `commons msg read`.
- Implement `commons msg reply`.
- Implement `commons msg ack`.
- Implement `commons context publish`.
- Implement `commons context request`.
- Implement `commons status`.
- Implement `commons status --json`.

#### Exit Criteria

- Two fake agents can register, publish plans, exchange messages, and update tasks.
- Human-readable `commons status` shows useful current state.
- JSON contracts are stable enough for agent use.

### Milestone 4: Resource Registry and Lease Engine

Goal: make shared resource ownership deterministic.

#### Subtasks

- Implement resource canonicalization.
- Implement resource aliases.
- Implement resource hierarchy and policy groups.
- Implement lease compatibility matrix.
- Implement `commons lease acquire`.
- Implement `commons lease renew`.
- Implement `commons lease release`.
- Implement `commons lease list`.
- Implement `commons lease conflicts`.
- Implement `commons lease force-release` with guarded policy.
- Implement DB transaction for lease acquisition.
- Add per-resource `fencing_epoch`.
- Increment `fencing_epoch` on each successful fencing-capable lease grant; observational grants retain the current epoch.
- Verify `lease_id + fencing_epoch` on renew/release/check.
- Mark expired leases without deleting them.
- Implement stale holder recovery states.
- Add denial/remediation output contract.
- Add concurrent acquire tests.
- Add expired lease recovery tests.
- Add old epoch rejection tests.

#### Exit Criteria

- Concurrent conflicting lease requests cannot both succeed.
- Old leases cannot release or renew newer leases.
- Denials are deterministic and actionable.
- Resource alias tests prevent bypass by alternate names.

### Milestone 5: Policy Gate and Wrappers

Goal: deliver Level 2 Enforced Local Coordination for configured operations.

#### Subtasks

- Implement policy evaluation engine.
- Implement project policy config.
- Implement risky command pattern config.
- Implement `commons run`.
- Record `operation.started`.
- Record `operation.completed`.
- Record `operation.failed`.
- Prevent wrapped command execution after policy denial.
- Implement wrapper environment isolation.
- Implement explicit lease checkpoint checks for long-running operations.
- Implement `commons deploy staging`.
- Implement `commons db migrate`.
- Implement `commons git push`.
- Implement `commons browser claim`.
- Implement `commons server restart`.
- Add fake deploy target.
- Add fake DB migration target.
- Add fake git remote target.
- Add fake browser profile target.
- Add fake server restart target.
- Add command spy and side-effect guard tests.

#### Exit Criteria

- Fake deploy contention is blocked before command execution.
- Fake DB migration contention is blocked before command execution.
- Fake git push conflict is blocked before command execution.
- Operation audit accurately reflects what executed and what was denied.

### Milestone 6: Skill, Filesystem Board, and Runtime Setup

Goal: deliver Level 1 Advisory Coordination for Codex and Claude Code.

#### Subtasks

- Finalize universal Commons Skill text.
- Create Codex skill installer.
- Create Claude Code skill installer.
- Add runtime-specific doctor checks.
- Add setup report for Codex.
- Add setup report for Claude Code.
- Finalize filesystem board contract.
- Implement board sync for agents.
- Implement board sync for tasks.
- Implement board sync for plans.
- Implement board sync for messages and inboxes.
- Implement board sync for leases.
- Implement board sync for status.
- Implement board sync for audit JSONL.
- Add `commons board path`.
- Add `commons board sync`.
- Add board contract tests.
- Add runtime contract tests.
- Add real Codex smoke test where available.
- Add real Claude Code smoke test where available.

#### Exit Criteria

- Codex can register, publish a plan, send a message, and request a lease.
- Claude Code can register, publish a plan, send a message, and request a lease.
- Missing runtime or auth causes a skipped runtime test with an explicit reason.

### Milestone 7: Hooks and Runtime Enforcement Adapters

Goal: connect runtime command interception where possible.

#### Subtasks

- Define runtime enforcement capability matrix.
- Implement Codex hook adapter where supported.
- Implement Claude Code `PreToolUse` hook adapter.
- Implement session-start registration hook.
- Implement pre-command policy hook.
- Implement post-command audit hook.
- Implement session-stop lease cleanup summary.
- Add non-blocking warning mode.
- Add blocking mode tests for runtimes that support blocking.
- Add bypass documentation.
- Add `commons doctor` hook validation.

#### Exit Criteria

- Blocking-capable runtimes block configured risky commands.
- Non-blocking runtimes show clear warning and write audit.
- Documentation does not overstate hook enforcement.

### Milestone 8: Realtime Events and Watch UX

Goal: make coordination visible without manual polling.

#### Subtasks

- Implement event outbox dispatcher.
- Implement SSE endpoint.
- Implement WebSocket endpoint.
- Implement replay by `Last-Event-ID`.
- Implement client de-duplication guidance.
- Implement `commons watch`.
- Implement `commons status --watch`.
- Add message notification events.
- Add lease conflict notification events.
- Add stale agent notification events.
- Add reconnect tests.
- Add outbox replay tests.
- Add event ordering tests.

#### Exit Criteria

- Realtime clients can disconnect and recover missed events.
- Humans can watch active agents, messages, leases, and conflicts.
- Documentation clearly states that event streams do not automatically wake idle LLM sessions.

### Milestone 9: Test Harness and Golden Path Automation

Goal: prove the product path with deterministic and runtime tests.

#### Subtasks

- Implement `commons test e2e`.
- Add scenario manifest format.
- Add temp HOME support.
- Add temp daemon support.
- Add temp SQLite database support.
- Add isolated port allocation.
- Add fake-agent adapter.
- Add codex-agent adapter.
- Add claude-agent adapter.
- Add prompt fixture support.
- Add transcript capture.
- Add command spy.
- Add fake resource logs.
- Add JSON result report.
- Add failure artifact bundle.
- Add redaction report.
- Add golden path scenario.
- Add staging contention scenario.
- Add DB migration handoff scenario.
- Add branch conflict scenario.
- Add prompt injection scenario.
- Add audit replay scenario.
- Split PR CI, nightly CI, and manual gates.

#### Exit Criteria

- PR CI proves simulator, CLI, fake-resource, audit, and redaction behavior.
- Nightly or manual tests prove real Codex/Claude runtime connection where available.
- Golden path is reproducible.

### Milestone 10: Security and Privacy Hardening

Goal: reduce leaks and make Local Mode honest and safer.

#### Subtasks

- Write detailed Local Mode threat model.
- Write detailed Team Mode threat model draft.
- Implement transport hardening.
- Add token storage rules.
- Remove sensitive values from normal output.
- Prevent tokens and fencing epochs from entering audit exports.
- Implement server-side capability grants.
- Implement artifact path canonicalization.
- Reject path traversal.
- Reject unsafe symlink attachment.
- Copy artifact snapshots.
- Implement secret scanning before persistence.
- Quarantine secret-risk artifacts.
- Add `human-only` visibility path.
- Sanitize markdown, ANSI, links, and HTML in displayed untrusted content.
- Add prompt-injection fixture tests.
- Add tamper-evident audit verification command.

#### Exit Criteria

- Secret-risk content is not visible to other agents by default.
- Audit hash chain can be verified.
- Prompt-injection tests verify that malicious messages do not execute commands.
- Docs accurately state remaining security limits.

### Milestone 11: Human Observability

Goal: make Commons understandable during daily work.

#### Subtasks

- Improve `commons status` layout.
- Add resource timeline command.
- Add task timeline command.
- Add message thread view.
- Add conflict view.
- Add stale session view.
- Add approval queue view.
- Add Markdown export.
- Add HTML report export.
- Add optional TUI prototype.
- Validate one-minute comprehension with manual tests.

#### Exit Criteria

- A user can understand active work, conflicts, and next actions quickly.
- A completed multi-agent task can be reconstructed from export alone.

### Milestone 12: Team Mode

Goal: support multiple users and hosts without inheriting Local Mode's weak trust model.

#### Subtasks

- Implement Postgres backend.
- Implement Postgres migrations.
- Implement multi-host agent presence.
- Implement authenticated access.
- Implement principal model.
- Implement capability authorization.
- Implement per-project resource policy.
- Implement token revocation.
- Implement TLS or mTLS deployment guidance.
- Implement artifact ACLs.
- Implement admin audit.
- Evaluate NATS JetStream.
- Evaluate Redis Streams.
- Add multi-host lease tests.
- Add team security review.

#### Exit Criteria

- Two machines can coordinate against one shared resource.
- Unauthorized principals cannot acquire restricted leases.
- Team Mode has a separate security review.

### Milestone 13: Ecosystem Bridges

Goal: interoperate without weakening Commons policy.

#### Subtasks

- Design optional MCP Agent Mail import/export bridge only if needed later.
- Design A2A bridge.
- Design Agent Client Protocol launcher bridge if useful.
- Add GitHub issue/PR annotations.
- Add Slack notification bridge.
- Add Linear notification bridge.
- Add import/export mapping.
- Add bridge security review.
- Add bridge contract tests.

#### Exit Criteria

- Commons can exchange useful task or message state with at least one external system.
- External bridges cannot bypass resource policy.

### Milestone 14: GA Hardening

Goal: make Commons stable enough for regular team use.

#### Subtasks

- Freeze stable CLI contract.
- Freeze stable filesystem board contract.
- Add backward-compatible migration tests.
- Add backup and restore.
- Add performance benchmarks.
- Add load tests for event replay.
- Add packaging installers.
- Add full documentation site.
- Add upgrade guide.
- Add troubleshooting guide.
- Complete security review.
- Complete release checklist.

#### Exit Criteria

- Another developer can install and use Commons without handholding.
- No known high-severity issues remain.
- Upgrade and backup paths are documented and tested.

## Release Gates

### Developer Preview Gate

Required:

- Milestones 0-4 complete.
- `commons init`, `commons up`, and `commons status` work.
- Fake agents can coordinate.
- Lease engine passes concurrency tests.
- `commons run` blocks fake conflicts.

Not promised:

- real Codex/Claude enforcement
- Team Mode
- strong same-user process security

### Private Beta Gate

Required:

- Milestones 0-9 complete.
- Codex and Claude Code runtime smoke tests pass where available.
- Golden path passes.
- Runtime setup is documented.
- Hooks or wrappers protect configured high-risk commands.
- Prompt-injection test passes.

Not promised:

- malicious same-user process isolation
- reliable idle-agent wakeup across all runtimes
- Team Mode security

### Public Beta Gate

Required:

- Milestones 0-11 complete.
- Setup can be completed on a clean local machine within 10 minutes.
- Audit exports are useful.
- Secret redaction and artifact quarantine are implemented.
- Manual daily-use acceptance passes.

### GA Gate

Required:

- Milestones 0-14 complete or explicitly deferred.
- Team Mode security review complete if Team Mode is included.
- Stable CLI and filesystem board contracts.
- Backup, restore, migration, and upgrade paths tested.
- Documentation complete.
