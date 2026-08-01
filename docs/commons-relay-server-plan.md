# Commons Relay Server Plan

> **Document status:** Delivery record for the Relay workstream. The baseline
> private Relay, remote CLI, tasks, messages, leases, Console, and deployment
> path shipped by 0.3.0. Use
> [Implementation Status](commons-implementation-status.md) for the current
> boundary and [Roadmap](commons-roadmap.md) for remaining work.

## Purpose

Commons Relay Server extends Commons from a single-machine coordination layer
into a self-hosted private coordination service. The baseline release lets
agents on different machines register, publish plans, exchange messages,
inspect inboxes, and coordinate shared resources through one remote authority
operated by their own team or organization.

The relay is not a replacement for Local Mode. Local Mode remains an explicit
single-machine option after workspace enrollment. The relay is the optional
Private Relay mode for cross-machine agent coordination.

Commons does not provide a hosted public relay network. A relay server is a
private trust boundary for a team, company, or individual developer.

## Requirements

### Functional Requirements

- Remote agents can register against a shared relay.
- Remote agents can list active agents in a project.
- Remote agents can send direct and broadcast messages.
- Remote agents can fetch and acknowledge their inbox.
- Remote agents can publish context packets as structured messages.
- Remote agents can acquire, list, and release resource leases.
- Lease decisions are made atomically by the relay, not by each client.
- Messages and lease decisions are auditable.
- The local `commons` CLI can talk to the relay without requiring MCP.
- Codex and Claude Code can keep using the Commons Skill and CLI.
- The relay exposes a health endpoint for deployment checks.
- The relay can run on a small VPS with no external dependencies.

### Non-Functional Requirements

- The first deployable version must use only the Python standard library.
- The relay must store state durably in SQLite WAL.
- Every mutating endpoint must require bearer-token authentication.
- The HTTP API must never expose secrets in normal responses.
- The relay must bind to localhost by default and require explicit host config to
  listen on other interfaces.
- Deployment must support systemd on Ubuntu/Debian servers.
- The relay must be testable locally with temporary state directories.
- The relay must support a later Postgres backend without changing the CLI
  contract.

## Test Boundaries

### Unit Tests

Unit tests prove:

- Relay database migrations create the expected tables.
- Agent registration is idempotent by `project_id + agent_id`.
- Message delivery writes sender, recipient, inbox, and audit rows.
- Inbox fetch supports unread-only and acknowledgement.
- Lease conflict rules match Local Mode rules.
- Expired leases do not block new leases.
- Bearer-token auth blocks unauthenticated mutation.

Unit tests do not prove:

- Network reachability outside the local test process.
- DNS or TLS correctness.
- Real Codex or Claude Code behavior.

### Local E2E Tests

Local E2E tests prove:

- A relay server can start on an ephemeral local port.
- Two simulated agents can register through the CLI.
- Agent A can send a message to Agent B through the relay.
- Agent B can fetch and acknowledge that message.
- Agent A can acquire a remote lease.
- Agent B is denied a conflicting remote lease.
- Agent A can release the lease and Agent B can acquire it.

Local E2E tests do not prove:

- Internet routing.
- Server reboot survival.
- TLS certificate issuance.

### Remote Deployment Tests

Remote deployment tests prove:

- The relay deploys to the configured server.
- The systemd service starts and restarts cleanly.
- `/health` responds through the configured private relay URL.
- The local CLI can use the relay over HTTP.
- Two local simulated agents can communicate through the remote relay.
- A remote lease conflict is enforced by the server.

Remote deployment tests do not prove:

- DNS for the operator's relay domain until the record is configured.
- HTTPS until DNS points at the server and certificates are issued.
- Malicious same-token isolation.

## Architecture

```text
Codex / Claude Code / Shell
  |
  | Commons Skill
  v
commons CLI
  |
  | Local Mode                       Private Relay Mode
  |                                  |
  | SQLite + ~/.commons/board        HTTP + bearer token
  |                                  |
  v                                  v
local Commons state             Commons Relay Server
                                      |
                                      v
                              SQLite WAL relay state
```

## Relay API

The first API version is `/v1`.

### Health

```http
GET /health
```

Returns:

```json
{"ok": true, "service": "commons-relay"}
```

### Agents

```http
POST /v1/agents/register
GET /v1/agents?project_id=...
```

Registration body:

```json
{
  "project_id": "commons-demo",
  "agent_id": "agent_local_a",
  "runtime": "codex",
  "workspace": "project",
  "user_name": "Sergio",
  "handle": "sergio-codex-a",
  "name": "Sergio-codex-a",
  "task_id": "task_123"
}
```

As of 0.4.0, every new Agent registration requires `user_name` and a handle
whose prefix matches the normalized user name. The CLI constructs these fields;
custom clients must follow the same contract. Pre-0.4.0 Agent rows remain
readable during migration.

### Messages

```http
POST /v1/messages
GET /v1/inbox?project_id=...&agent_id=...&unread_only=true&limit=200&cursor=...&envelope=true
GET /v1/messages/{message_id}?project_id=...&agent_id=...
POST /v1/messages/{message_id}/ack
```

Message body:

```json
{
  "project_id": "commons-demo",
  "sender_agent_id": "agent_a",
  "recipient_agent_id": "agent_b",
  "thread_id": "thread_demo",
  "message_type": "note",
  "body": "I need staging after your deploy."
}
```

Inbox envelope responses contain `messages` and a `page` object. The relay enforces a 200-message HTTP page cap and reports `server_limit`, `has_more`, `window_complete`, and `next_cursor`. Cursors use the monotonic SQLite message sequence, so concurrent newer writes do not enter an older traversal. During the compatibility window, a request without `envelope=true` receives a legacy array. Message acknowledgements and broadcast audience snapshots are per agent, and messages remain retrievable by id after they leave the current inbox window.

### Leases

```http
POST /v1/leases/acquire
GET /v1/leases?project_id=...&active=true
POST /v1/leases/{lease_id}/renew
POST /v1/leases/{lease_id}/release
```

Lease acquire body:

```json
{
  "project_id": "commons-demo",
  "resource_id": "deploy-slot:commons-demo/staging",
  "mode": "exclusive",
  "holder_agent_id": "agent_a",
  "ttl_seconds": 1800,
  "reason": "Deploy staging"
}
```

Conflict response:

```json
{
  "error": "lease conflict",
  "details": {
    "resource_id": "deploy-slot:commons-demo/staging",
    "holder_agent_id": "agent_a",
    "holder_handle": "codex-alpha",
    "holder_contact_code": "C7DX92",
    "holder_lease_id": "lease_123",
    "holder_mode": "exclusive",
    "coordination_recipient": "@codex-alpha",
    "safe_next_actions": [
      "commons remote msg send @codex-alpha 'Can you release deploy-slot:commons-demo/staging when done?' --remote default --project commons-demo --sender agent_b",
      "commons remote lease list --remote default --project commons-demo --active"
    ]
  }
}
```

The CLI rewrites these actions with the actual local remote name before showing
the denial, so each returned command can be executed directly even when the
relay is configured under a name other than `default`.

## CLI Contract

### Configuration

```bash
commons remote add default --url https://relay.example.internal --token-env COMMONS_RELAY_TOKEN --project commons-demo
commons remote status --remote default
```

### Agent Registration

```bash
commons remote agent register --remote default --project commons-demo --agent agent_a --runtime codex
commons remote agent list --remote default --project commons-demo
```

### Messages

```bash
commons remote msg send @agent_b "hello" --remote default --project commons-demo --sender agent_a
commons remote inbox --remote default --project commons-demo --agent agent_b
commons remote msg ack msg_123 --remote default --project commons-demo --agent agent_b
```

### Leases

```bash
commons remote lease acquire deploy-slot:commons-demo/staging --mode exclusive --remote default --project commons-demo --agent agent_a
commons remote lease list --active --remote default --project commons-demo
commons remote lease renew lease_123 --remote default --project commons-demo --agent agent_a --fencing-epoch 42 --ttl 30m
commons remote lease release lease_123 --remote default --project commons-demo --agent agent_a --fencing-epoch 42
```

## Security Baseline

- All mutating endpoints require `Authorization: Bearer <token>`.
- Read endpoints also require the token in the first release.
- Token comes from `COMMONS_RELAY_TOKEN` or a configured token env var.
- The server does not support anonymous writes.
- The server stores only coordination metadata, not private prompts or secrets.
- Message bodies are treated as untrusted text by clients.
- The relay is not suitable as a public multi-tenant service for untrusted users.
- Handles and contact codes are scoped to one relay project, not globally unique.
- Future releases can add scoped tokens, token rotation, and admin audit.

## Deployment Plan

Target server placeholders:

```text
relay.example.internal
ssh -i ~/.ssh/commons-relay deploy@relay.example.internal
```

Initial deployment:

- Clone `git@github.com:t54-labs/agent-commons.git`.
- Install Python 3.11+ if needed.
- Create `/etc/commons-relay.env` with `COMMONS_RELAY_TOKEN`.
- Create `/var/lib/commons-relay` for state.
- Start `commons relay serve` under systemd.
- Bind to `127.0.0.1:8766` and put HTTPS reverse proxy in front of it.
- Keep direct relay ports private.

DNS request:

```text
relay.example.internal. 300 IN A <relay-server-ip>
```

After DNS:

- Configure reverse proxy on ports 80/443.
- Issue TLS certificate.
- Use `https://relay.example.internal` as the client endpoint.
- Firewall direct port `8766` unless it is bound only to localhost.

## Milestones and Subtasks

### Milestone R0: Relay Roadmap and Contract

Goal: define the deployable relay contract before implementation.

Subtasks:

- Define relay purpose and non-goals.
- Define test boundaries.
- Define HTTP API.
- Define CLI contract.
- Define deployment plan.
- Define DNS handoff.

Exit criteria:

- This document is committed.

### Milestone R1: Relay Core

Goal: implement the relay state engine and HTTP API.

Subtasks:

- Add relay SQLite schema.
- Add relay service functions.
- Add relay HTTP server.
- Add bearer-token middleware.
- Add health endpoint.
- Add agent register/list endpoints.
- Add message send/inbox/ack endpoints.
- Add lease acquire/list/renew/release endpoints.
- Add audit event rows.

Exit criteria:

- Unit tests cover service logic and HTTP auth.

### Milestone R2: CLI Integration

Goal: expose relay operations through `commons remote`.

Subtasks:

- Add remote config storage.
- Add `commons remote add`.
- Add `commons remote status`.
- Add `commons remote agent register/list`.
- Add `commons remote msg send/inbox/ack`.
- Add `commons remote lease acquire/list/renew/release`.
- Add JSON output for every command.
- Add human-readable output where useful.

Exit criteria:

- CLI can complete local relay E2E against an ephemeral server.

### Milestone R3: Skill and Docs Update

Goal: teach agents how to use relay mode safely.

Subtasks:

- Add Relay Mode section to Commons Skill.
- Document startup checks for local and remote inboxes.
- Document when to acquire local vs remote leases.
- Document secret handling for relay tokens.
- Update README quick start.
- Update implementation status.

Exit criteria:

- Installed skill remains local-first but includes relay commands when configured.

### Milestone R4: Local E2E

Goal: prove remote behavior without a real network.

Subtasks:

- Start relay on a local ephemeral port in tests.
- Register two simulated agents.
- Send/fetch/ack a message.
- Acquire/release a lease.
- Assert conflict denial.
- Assert audit rows exist.

Exit criteria:

- Unit suite and local relay E2E pass.

### Milestone R5: Server Deployment

Goal: deploy the relay to the provided GCP server.

Subtasks:

- SSH to the server.
- Clone or update the Commons repo.
- Install runtime prerequisites.
- Configure relay token.
- Create state directory.
- Install systemd service.
- Start and enable service.
- Verify `/health`.
- Verify remote CLI status from local machine.

Exit criteria:

- `https://relay.example.internal/health` returns ok.

### Milestone R6: Remote E2E

Goal: prove local agents can communicate through the deployed relay.

Subtasks:

- Configure local `commons remote default`.
- Register simulated Codex agent A.
- Register simulated Claude Code agent B.
- Send message A to B.
- Fetch and acknowledge B inbox.
- Acquire remote lease as A.
- Confirm B is denied conflicting lease.
- Release lease as A.
- Confirm B can acquire after release.

Exit criteria:

- E2E report is attached or printed with message ids and lease ids.

### Milestone R7: DNS and HTTPS Follow-Up

Goal: move from IP endpoint to stable domain.

Subtasks:

- Create `A relay.example.internal -> <relay-server-ip>`.
- Wait for DNS propagation.
- Configure reverse proxy.
- Issue TLS certificate.
- Update relay URL to `https://relay.example.internal`.
- Re-run remote E2E.

Exit criteria:

- `https://relay.example.internal/health` returns ok.
