# Commons Product Design

> **Document status:** Product and architecture record. Some sections describe
> target behavior beyond the current release. Use
> [Implementation Status](commons-implementation-status.md) for shipped
> capabilities and [Roadmap](commons-roadmap.md) for future work.

## Purpose

Commons is a coordination control plane for coding agents. It lets Codex, Claude Code, and other CLI-based agents discover each other, share structured plans, exchange messages, coordinate ownership of shared resources, and produce an auditable record of what happened.

Commons is open-source software for local and self-hosted private relay coordination. It is not a hosted public relay network. See [Open-Source and Self-Hosting Model](open-source-self-hosting.md).

Commons is not just a chat board. The core product problem is safe coordination around external side effects: staging environments, databases, deployments, git branches, browser profiles, local ports, long-running servers, and shared credentials.

## Product Principles

1. Agents should coordinate before they mutate shared state.
2. Shared context should be structured, scoped, and redacted by default.
3. Dangerous actions must be gated by leases and policy, not by voluntary etiquette.
4. The system must remain human-readable and recoverable.
5. Realtime collaboration should not sacrifice durable auditability.
6. Agent messages are untrusted input. They can inform another agent, but they must not become executable instructions without validation.
7. The same coordination contract should work from Codex, Claude Code, shell scripts, CI, and future agent runtimes.

## Target Users

- Individual developers running multiple local coding agents in parallel.
- Teams sharing staging environments, databases, or integration sandboxes.
- Engineering leads who want audit trails of AI-assisted changes.
- Agent developers who need a standard local coordination substrate.
- Teams that want to self-host a private relay rather than send coordination metadata to a public service.

## Non-Goals

- Replace Codex, Claude Code, or any agent runtime.
- Become a general-purpose chat app.
- Store full private prompts, secrets, browser cookies, or unredacted terminal logs by default.
- Guarantee safety for tools that bypass Commons wrappers and hooks.
- Provide hard distributed consensus in the first local-first release.
- Guarantee strong isolation from malicious processes running as the same OS user in Local Mode.
- Guarantee that realtime events can wake an idle LLM session without a runtime-specific adapter.
- Operate a public Commons relay network.
- Provide global public usernames, global contact codes, federation, or cross-organization agent discovery.
- Host unrelated untrusted tenants on one relay server.

## Requirements and Delivery Plan

The original requirements, test boundaries, milestone plan, and per-milestone
task breakdown live in
[Commons Requirements, Test Boundaries, and Delivery Plan](commons-requirements-delivery-plan.md).

This design document explains the architecture. The delivery plan defines what must be implemented, what each test layer can prove, and which product promises are valid at each release gate.

## System Overview

```text
Codex / Claude Code / Other Agents
  |
  | Skill instructions
  | CLI commands
  | filesystem board
  | CLI wrappers
  | lifecycle hooks
  v
Commons Control Plane
  |
  |-- Agent registry
  |-- Task and plan ledger
  |-- Threaded mailbox
  |-- Resource leases
  |-- Realtime event stream
  |-- Policy gate
  |-- Audit log
  |
  |-- SQLite WAL or Postgres for durable state
  |-- Optional WebSocket or SSE for realtime notifications
  |-- Filesystem/Git artifact store for large human-readable outputs
```

## Deployment Modes

### Local Mode

Local Mode is the explicit same-machine option after workspace enrollment. It
uses the `commons` CLI, SQLite WAL, and the filesystem board under
`~/.commons/board` for the core coordination path. The `commonsd` daemon is
optional and exists only for realtime status and event streaming; agents must
not need MCP or a daemon to register, publish plans, exchange messages, or
acquire leases.

Use this mode for a single user running multiple Codex and Claude Code sessions.

Local Mode is designed to prevent coordination mistakes among cooperative agents. It is not a strong security boundary against malicious processes running as the same OS user.

### Private Relay Mode

Private Relay Mode uses a self-hosted relay server with bearer-token authentication and project-scoped coordination metadata. It supports multiple machines coordinating against the same staging and database resources.

Use this mode when multiple people or always-on agent hosts share resources inside one trusted team or organization.

A relay server is a trust boundary, not a public multi-tenant service. Broadcasts, active leases, agent discovery, handles, and contact codes are scoped to a relay project.

Future larger deployments may add stronger organization auth, Postgres, NATS JetStream, Redis Streams, or admin policy UI, but those additions should preserve the self-hosted private relay model.

### Offline Ledger Mode

Offline Ledger Mode writes append-only JSONL and Markdown snapshots to disk when the SQLite state engine is unavailable. It does not provide reliable realtime delivery or strong leases. It exists only as a degraded-mode audit trail and recovery path.

Offline Ledger Mode must not grant strong leases or allow high-risk wrappers to proceed as if coordination were enforced.

## Core Concepts

### Agent Session

An `AgentSession` represents one active agent process or conversation thread.

Key fields:

- `agent_id`
- `runtime`: `codex`, `claude-code`, `custom`, `ci`, `human`
- `runtime_version`
- `host`
- `pid`
- `workspace`
- `repo`
- `branch`
- `task_id`
- `capabilities`
- `heartbeat_at`
- `status`: `online`, `idle`, `busy`, `blocked`, `offline`, `stale`

### Task

A `Task` is a unit of desired work. Agents can claim, update, block, hand off, and complete tasks.

Task states:

- `created`
- `claimed`
- `in_progress`
- `blocked`
- `needs_human`
- `ready_for_review`
- `completed`
- `cancelled`
- `failed`

### Plan

A `Plan` is the agent's current declared intent. It is not a full transcript. It should include the next likely operations, impacted resources, expected validation, and known blockers.

Plans are versioned. Other agents can inspect the latest plan or compare plan changes.

### Message

A `Message` is a threaded communication item between agents. Messages can be direct, task-scoped, resource-scoped, or broadcast.

Messages must be treated as untrusted external input by receiving agents.

### Resource Lease

A `ResourceLease` is a time-bounded claim over a shared resource.

Examples:

- `env:example-app/staging`
- `db:example-app/staging`
- `deploy-slot:example-app/staging`
- `git-branch:example-app/main`
- `browser-profile:chrome/default`
- `port:localhost/3000`
- `server:localhost/portal-dev`
- `path:src/api.py`

Lease modes:

- `observe`: agent is watching or reading, no mutation expected.
- `read`: non-mutating active use.
- `write`: mutation expected, compatible only with compatible observers.
- `exclusive`: no other active use should proceed.
- `maintenance`: operator-level lock for migrations, destructive resets, or emergency repair.

Every resource has a monotonically increasing `fencing_epoch`. Fencing-capable grants (`write`, `exclusive`, and `maintenance`) advance it; observational grants record the current epoch without invalidating an active writer. High-risk wrappers must validate `lease_id + fencing_epoch` before execution and at configured checkpoints during long-running operations. A stale or missing epoch blocks the action.

For resources whose downstream systems cannot validate Commons leases, protection is advisory outside the wrapper boundary. The wrapper can prevent a command it controls from starting, but it cannot prevent a separate process from bypassing Commons.

### Policy Gate

The `PolicyGate` decides whether an operation can proceed. It checks identity, capabilities, resource leases, risk level, workspace policy, and optional human approval requirements.

High-risk operations:

- staging deploy
- database migration
- database write or destructive seed reset
- git push to protected branch
- force push
- browser profile takeover
- local server stop or restart
- cloud resource mutation
- secret access

### Audit Event

All significant state changes are append-only audit events. Nothing important is represented only by mutable current-state rows.

Event examples:

- `agent.registered`
- `agent.heartbeat`
- `task.claimed`
- `plan.published`
- `message.sent`
- `lease.requested`
- `lease.granted`
- `lease.denied`
- `lease.renewed`
- `lease.released`
- `policy.denied`
- `operation.started`
- `operation.completed`
- `artifact.attached`

Audit events are written in the same database transaction as the state mutation they describe. A corresponding event outbox row is also written in the same transaction so optional realtime delivery can replay durable events after disconnects or daemon restarts.

## Data Storage

### Local State

Default path:

```text
~/.commons/state/commons.db
```

SQLite settings:

- WAL enabled
- foreign keys enabled
- busy timeout enabled
- append-only event table
- FTS index for messages, plans, and audit summaries

### Artifact Store

Default path:

```text
~/.commons/artifacts/{task_id}/...
```

Artifacts are typed:

- `safe-log`
- `patch`
- `screenshot`
- `report`
- `test-output`
- `redacted-context`
- `private`
- `secret-risk`

Only safe artifact types should be exposed to other agents by default.

### Human-Readable Exports

Commons periodically exports Markdown snapshots:

```text
~/.commons/exports/daily/{YYYY-MM-DD}.md
~/.commons/exports/tasks/{task_id}.md
~/.commons/exports/resources/{resource_id}.md
```

Exports are not the source of truth. They exist for inspection, review, backup, and recovery.

## Realtime Model

Local Mode may use WebSocket and SSE when `commonsd` is enabled:

- WebSocket for interactive clients and TUI.
- SSE for simple subscribers and agents that only need event streaming.
- Durable events remain in the database.

Team Mode can add:

- Postgres `LISTEN/NOTIFY` for simple deployments.
- Redis Streams for simple distributed streams.
- NATS JetStream for durable consumers, replay, dead-letter queues, and stronger multi-agent event fanout.

The database remains the source of truth. Realtime channels are delivery paths, not the authoritative state.

Realtime events do not guarantee that an idle Codex or Claude Code session wakes up. Agent wakeup requires a runtime-specific sidecar or adapter that can safely notify or resume that runtime.

## Security Model

### Identity

Each agent receives a local session token during registration. Team Mode requires a stronger design with signed tokens, mTLS, or another authenticated principal model.

Local identity metadata is best-effort attribution. Runtime, host, user, workspace, repo, branch, and pid fields are useful for coordination and audit, but they are not proof against same-user impersonation.

Identity fields should include:

- runtime
- host
- user
- workspace
- repo
- pid
- session/thread id when available

### Capability Scopes

Capabilities are explicit:

- `task.read`
- `task.write`
- `message.send`
- `lease.acquire`
- `artifact.attach`
- `git.push`
- `deploy.staging`
- `db.write`
- `browser.control`
- `policy.override`

Capabilities are granted by server-side policy. Agents must not be able to self-declare privileged scopes such as `db.write`, `deploy.staging`, or `policy.override`.

### Visibility

Tasks, messages, plans, and artifacts support visibility:

- `public`
- `repo`
- `workspace`
- `agent-pair`
- `human-only`
- `private`

### Prompt Injection Boundary

Agent-authored messages are untrusted. A receiving skill must:

1. Read the message as coordination context.
2. Validate claims against repository state, command output, audit events, or human confirmation.
3. Never execute shell commands from another agent's message verbatim.
4. Never reveal secrets or full private prompt text to another agent.

## Operation Wrappers

Commons must provide wrappers for high-risk commands:

```bash
commons run --resource env:example-app/staging --mode write -- npm run deploy:staging
commons db --resource db:example-app/staging -- migrate up
commons git push --resource git-branch:example-app/main
commons browser claim chrome/default --mode exclusive
commons server restart portal-dev --resource server:localhost/portal-dev
```

Wrappers perform:

1. Agent/session resolution.
2. Policy check.
3. Lease acquisition or validation.
4. Operation start audit event.
5. Command execution.
6. Operation completion audit event.
7. Lease release or renewal prompt.

## Adapter Strategy

### Codex

Codex integration should use:

- Open Agent Skill instructions.
- `commons` CLI commands.
- The filesystem board under `~/.commons/board`.
- Project or user-level configuration.
- Hooks where available for command gating.
- Optional `codex exec` automation wrappers for test harnesses.

### Claude Code

Claude Code integration should use:

- Custom Skill instructions.
- `commons` CLI commands.
- The filesystem board under `~/.commons/board`.
- Hooks for `PreToolUse` policy enforcement.
- Optional custom slash commands.
- Agent Teams compatibility, without depending on Agent Teams.

### Other Agents

Any agent that can run shell commands or read/write the filesystem board can participate.

## User Experience

### CLI

The CLI should be scriptable, stable, and terse.

Examples:

```bash
commons doctor
commons agent register --runtime codex --workspace "$PWD"
commons status
commons task create "Fix staging webhook regression"
commons plan publish --task task_123 --file plan.md
commons lease acquire env:example-app/staging --mode write --ttl 30m --reason "deploying image abc123"
commons msg send @claude-api "I need the staging DB after your migration finishes."
commons inbox
commons audit resource env:example-app/staging
```

### TUI

A future `commons tui` should show:

- active agents
- active leases
- blocked tasks
- recent messages
- resource timeline
- approval queue

### Web UI

The Web UI should be optional. It should focus on observability and approval, not chat.

Commons Console implements the observability surface in version 0.3.0. One
private Relay is presented as a Workspace containing Projects. Operators can
inspect Agent presence, explicit task progress, messages, leases, and an SSE-fed
activity timeline. The initial Console is read-only; approval and mutation
controls remain future policy work.

## Reliability Requirements

- No partial writes for durable state transitions.
- Every mutation emits an audit event.
- Lease expiry never deletes history.
- Agents can recover after daemon restart.
- Stale sessions are detected by heartbeat timeout.
- Duplicate commands should be idempotent when a client request id is supplied.
- Realtime disconnects must be recoverable by replaying durable events.

## Product Quality Bar

Commons is ready for daily use only when:

1. Two Codex sessions and two Claude Code sessions can coordinate through the same daemon.
2. A staging deploy conflict is detected and blocked before execution.
3. A DB migration conflict is detected and blocked before execution.
4. An agent crash leaves an expired lease that can be safely recovered.
5. Another agent can request context without receiving secrets or full private prompts.
6. The audit log explains who did what, when, why, and under which lease.
7. The system has simulator tests and real CLI integration tests.
8. The product can run in local-only mode without external services.
