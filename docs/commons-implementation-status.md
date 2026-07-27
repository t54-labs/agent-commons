# Commons Implementation Status

This document records the current implemented product boundary for Commons.

## Implemented Scope-First Self-Hosted Product

Commons is currently implemented as a scope-first coordination product with remote, local-only, and disabled workspace modes. The relay is self-hosted private infrastructure; Commons does not provide a hosted public relay network.

- `commons` CLI with JSON output support.
- SQLite WAL local state.
- Filesystem board under `~/.commons/board`.
- Codex and Claude Code skill installation through `commons install-skill`.
- Workspace scope resolution and enrollment through project config and global workspace rules.
- Optional lightweight private relay server using HTTP, bearer-token auth, and SQLite WAL.
- Remote CLI config under `~/.commons/remotes.json` without storing token values; clients can use an environment variable or a `0600` token file whose POSIX permissions are enforced before reading.
- Remote agent registration with absolute-path redaction by default, human-readable handles, explicit or generated short contact codes, handle-conflict suggestions, evidence-based activity with mandatory Skill heartbeats, authenticated project status, discovery, direct/broadcast messages, cursor-paginated inbox reads, durable message retrieval by id, active-at-send broadcast audience snapshots, per-agent message receipts, lease acquire/list/renew/release, and project-scoped audit reads.
- Remote project registry plus first-class task create/update/list/show with explicit status, owner, current step, next step, blockers, optional agent-reported progress, dependencies, and optimistic versions.
- Commons Console operator UI with Team-token or optional separate Console-token exchange, signed HttpOnly sessions, multi-project overview, Agent details, task progress, messages, leases, activity timelines, responsive layouts, and SSE refresh.
- Relay-enforced uniqueness for agent handles and contact codes within each relay project.
- Agent registration, heartbeat, unregister, status, and discovery.
- Task create, claim, update, block, unblock, complete, fail, cancel, show, and list.
- Versioned plans with show and diff.
- Direct messages, broadcast messages, file-backed messages, replies, inbox, read, and ack.
- Context publish/request/show.
- Resource registry, aliases, inspect, and list.
- Lease engine with observe/read/write/exclusive/maintenance modes, namespaced canonical ids, separator and traversal normalization, local aliases, write-mode fencing epochs, owner-and-epoch-checked remote renew and release, atomic in-place TTL renewal, idempotent release, migration conflict blocking, force release, conflict checks, and persisted denial audit events.
- Generic wrapper plus deploy, DB migration, git push, browser profile, and server restart wrappers.
- Artifact attach/list/show with immutable snapshots, symlink/traversal rejection, basic text redaction, and `secret-risk` human-only visibility.
- Audit recent/task/resource filters, hash-chain verification, and Markdown task/resource exports.
- Optional `commonsd` daemon lifecycle and logs.
- `commons watch` and `commons status --watch`.
- Deterministic E2E scenarios for staging contention, DB handoff, branch conflict, browser takeover, prompt-injection message handling, and the golden path.
- Runtime smoke prepare/verify harness for real Codex and Claude Code sessions.

## Explicitly Deferred Tracks

These tracks remain product roadmap items and are not part of the current scope-first release:

- Advanced multi-host Team Mode with Postgres/NATS, organization auth, TLS automation, and admin policy UI.
- TUI beyond CLI watch/status and advanced Console mutation controls.
- Runtime command interception hooks that depend on runtime-specific hook support.
- Reliable idle-agent wakeup or automatic session resume.
- Optional MCP Agent Mail import/export bridge.
- Advanced policy hierarchy and approval workflows beyond local force-release audit.
- Full secret scanning equivalent to a dedicated DLP product.
- Versioned remote plan bodies, remote artifact snapshots, and full remote resource registry APIs. Remote tasks are first-class; plan bodies are still carried through task fields and typed broadcasts.
- Public relay hosting, global public usernames, global contact codes, federation, and cross-organization discovery.
- Rich UI for scope enrollment beyond the conversational Agent + CLI backend flow.

## Current Verification

The current implementation is verified by:

```bash
python3 -m unittest discover -s tests -v
commons doctor --project-dir "$PWD" --json
commons test e2e --scenario all --agents codex,claude-code --json
commons scope resolve --workspace "$PWD" --json
commons remote status --remote default --project <project>
commons audit verify --json
commons test runtime prepare --agents codex,claude-code --project-dir "$PWD" --json
```

The unit suite includes an end-to-end relay test that starts a real local relay process, proves authenticated and unauthenticated behavior, registers Codex and Claude Code agents with handles and contact codes, verifies duplicate handle/contact-code denial, sends and acknowledges a message, retrieves it durably by id, verifies lease conflict denial, releases the lease, and confirms another agent can acquire the resource. A separate relay test verifies the 200-message server page cap, explicit truncation metadata, cursor traversal, 500-message client aggregation, and independent broadcast receipts.

The Console suite builds the production frontend and runs Playwright against a real local Relay fixture on desktop and mobile Chromium. It verifies token-to-cookie login, multi-project switching, Agent details, task progress, direct and broadcast messages, lease history, SSE delivery, and horizontal-overflow boundaries.

The runtime smoke command generates prompt files under `~/.commons/runtime-tests/{run_id}`. Give those prompts to real Codex and Claude Code sessions, then run:

```bash
commons test runtime verify {run_id} --json
```
