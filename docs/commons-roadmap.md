# Commons Product Roadmap

## Vision

Commons should become the default local coordination layer for developers running multiple coding agents. It should make multi-agent work observable, safe, and useful without requiring the human to relay routine status between agents.

## North-Star Capabilities

1. Any Codex or Claude Code agent can discover active local agents.
2. Agents can exchange scoped messages and context packets.
3. Agents can publish current plans and next intended actions.
4. Shared resources are protected by leases and policy gates.
5. High-risk commands are wrapped or blocked unless Commons grants permission.
6. Humans can inspect the current state and replay the audit history.
7. The system works locally by default and scales to team mode later.
8. The product includes real cross-runtime E2E tests.

## Canonical Delivery Plan

The detailed requirements, test boundaries, development milestones, release gates, and per-milestone subtasks live in [Commons Requirements, Test Boundaries, and Delivery Plan](commons-requirements-delivery-plan.md).

Production-like agent feedback covering reliable inbox history, signed messages, durable commitments, typed payloads, canonical resources, lease waiters, presence, timelines, and remote tasks is tracked in [Commons Feedback Hardening and Trust Roadmap](commons-feedback-hardening-plan.md).

This roadmap is the short strategic view. The delivery plan is the implementation backlog.

## Milestone 0: Research and Product Contract

Status: design phase.

Deliverables:

- Product design.
- CLI and skill specification.
- E2E test plan.
- Architecture decisions.
- Open-source landscape notes.

Acceptance criteria:

- The product is clearly differentiated from a chat board.
- The first implementation target is clear.
- The test plan includes real Codex and Claude Code scenarios.

## Milestone 1: Local Control Plane Foundation

Goal: create a durable filesystem-first CLI that can coordinate fake agents without requiring MCP or a daemon.

Deliverables:

- `commons` CLI.
- SQLite WAL state.
- Filesystem board.
- Optional `commonsd` local daemon for realtime status/event streaming.
- Agent registry.
- Task ledger.
- Message ledger.
- Audit event table.
- JSON output for all CLI commands.
- `commons doctor`.

Acceptance criteria:

- Two simulator agents can register, create tasks, send messages, and emit audit events.
- State survives process restarts because SQLite and the filesystem board are the source of truth.
- CLI commands are scriptable and tested.

## Milestone 2: Resource Lease Engine

Goal: make external side effects visible and controllable.

Deliverables:

- Resource model.
- Lease modes and compatibility matrix.
- TTL and heartbeat.
- Stale lease detection.
- Fencing epochs.
- Lease conflict explanations.
- Force-release flow with audit and optional human approval.

Acceptance criteria:

- Conflicting leases are denied deterministically.
- Stale leases are recoverable without deleting history.
- Lease operations emit audit events.

## Milestone 3: Policy Gate and Command Wrappers

Goal: prevent risky operations from bypassing coordination.

Deliverables:

- `commons run`.
- `commons git push`.
- `commons db migrate`.
- `commons deploy staging`.
- `commons browser claim`.
- `commons server restart`.
- Configurable risky command patterns.
- Local policy file support.

Acceptance criteria:

- A staging deploy conflict is blocked before command execution.
- A DB migration conflict is blocked before command execution.
- Denials include a clear remediation path.

## Milestone 4: Skill and Filesystem Board Integration

Goal: make Codex and Claude Code know how to use Commons.

Deliverables:

- Universal Commons Skill.
- Codex packaging instructions.
- Claude Code packaging instructions.
- Filesystem board for agents, tasks, messages, plans, leases, artifacts, and audit.
- Board sync commands.
- Runtime-specific setup checker.

Acceptance criteria:

- A Codex agent can register, publish a plan, send a message, and acquire a lease.
- A Claude Code agent can do the same.
- The skill instructs agents to treat messages as untrusted context.

## Milestone 5: Hooks and Enforcement Adapters

Goal: move from voluntary coordination to practical enforcement.

Deliverables:

- Codex hook adapter where supported.
- Claude Code hook adapter.
- Pre-command policy check.
- Post-command audit recording.
- Session-start registration.
- Session-stop lease cleanup summary.

Acceptance criteria:

- Risky commands are detected.
- Blocking-capable runtimes block unauthorized commands.
- Non-blocking runtimes produce clear warnings and audit events.

## Milestone 6: Realtime UX

Goal: make coordination immediate enough for daily work.

Deliverables:

- WebSocket event stream.
- SSE event stream.
- Event replay from last seen event id.
- `commons watch`.
- `commons status --watch`.
- Notification hooks for conflicts and direct messages.

Acceptance criteria:

- Agents and humans can see lease and message changes without polling.
- Reconnects recover missed events from durable state.

## Milestone 7: End-to-End Test Harness

Goal: prove Commons works with real agent runtimes.

Deliverables:

- Simulator test suite.
- CLI integration suite.
- Fixture projects.
- Fake staging server.
- Fake DB/migration target.
- Real Codex test runner.
- Real Claude Code test runner.
- Artifact bundle on failure.

Acceptance criteria:

- Staging deploy contention test passes with Codex + Claude Code.
- DB migration handoff test passes with Codex + Claude Code.
- Prompt injection message test passes.
- Audit replay test passes.

## Milestone 8: Human Observability

Goal: make Commons easy to inspect and trust.

Deliverables:

- `commons tui`.
- Resource timeline views.
- Task timeline views.
- Agent presence view.
- Approval queue.
- Markdown exports.
- HTML report export.

Acceptance criteria:

- A human can understand active work in under one minute.
- A human can reconstruct a completed multi-agent task from export alone.

## Milestone 9: Team Mode

Goal: support multiple machines and always-on agent hosts.

Deliverables:

- Postgres backend.
- Optional NATS JetStream backend.
- Token-based auth.
- Capability scopes.
- Team resource registry.
- Multi-host presence.
- Admin policy.

Acceptance criteria:

- Two machines can coordinate against the same staging resource.
- Durable consumers can replay missed events.
- Capability policy can prevent unauthorized deploy or DB write.

## Milestone 10: Ecosystem Bridges

Goal: interoperate with adjacent standards and tools.

Deliverables:

- Optional MCP Agent Mail import/export bridge only if needed later.
- A2A task/message bridge.
- Agent Client Protocol launcher bridge if useful.
- GitHub issue/PR annotations.
- Slack or Linear notifications.
- CI mode for automated policy checks.

Acceptance criteria:

- Commons can exchange useful task state with at least one external agent coordination system.
- Bridges do not weaken local policy enforcement.

## Milestone 11: Hardening and GA

Goal: make Commons safe enough for routine daily use.

Deliverables:

- Threat model.
- Security review.
- Secret redaction.
- Backup and restore.
- Migration system.
- Performance benchmarks.
- Backward-compatible CLI contract.
- Documentation site.
- Installers.

Acceptance criteria:

- No known high-severity security issues.
- Database migrations are tested.
- Upgrade and downgrade paths are documented.
- Product can be installed and used by another developer without handholding.

## Release Tracks

### Developer Preview

Includes:

- optional local daemon
- CLI
- simulator tests
- basic leases
- manual skill instructions

Not yet safe for high-risk real staging use without human review.

### Private Beta

Includes:

- Codex + Claude Code skills
- filesystem board integration
- hooks
- staging and DB wrapper tests
- realtime status
- audit exports

Safe for controlled local use.

### Public Beta

Includes:

- robust installation
- TUI
- real E2E harness
- prompt-injection tests
- stale lease recovery
- documented security model

Safe for broader local use.

### GA

Includes:

- team mode
- policy scopes
- hardening
- migrations
- stable CLI
- stable filesystem board contract
- complete documentation

Safe for regular team workflows.

## Product Risks

### Agents May Bypass Commons

Mitigation:

- hooks
- wrappers
- project policies
- clear AGENTS.md and CLAUDE.md guidance
- high-risk command detection

### Shared Context May Leak Secrets

Mitigation:

- scoped visibility
- redaction
- artifact typing
- context packets instead of transcripts
- secret scanners

### Locks May Create False Safety

Mitigation:

- fencing epochs
- policy gates
- wrapper enforcement
- audit replay
- explicit degraded mode

### Too Much Ceremony May Reduce Adoption

Mitigation:

- good defaults
- auto-registration
- concise status output
- `commons run` for generic use
- skill-driven behavior

### Runtime Integrations May Drift

Mitigation:

- adapters with contract tests
- setup doctor
- real runtime E2E tests
- conservative skill instructions

## First Implementation Recommendation

Build the product in this order:

1. Product contract and threat model.
2. `commons init`, `commons up`, `commonsd`, SQLite, and CLI skeleton.
3. Agent registry, tasks, messages, plans, audit, and status output.
4. Resource registry, lease engine, and fencing epochs.
5. `commons run`, policy gate, and fake-resource wrapper tests.
6. Universal Commons Skill and filesystem board integration.
7. Codex and Claude Code runtime smoke tests.
8. Hooks and enforcement adapters.
9. Realtime watch and event replay.
10. E2E harness and golden path automation.
11. Security hardening, observability, team mode, bridges, and GA hardening.

This order validates the coordination core before investing in UI and distributed infrastructure.
