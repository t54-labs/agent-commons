# Why Commons

## The Problem Is No Longer Parallelism

Coding tools can already run multiple agents at once. The harder problem begins
when independently started sessions share the same engineering world.

One Agent is preparing a deployment while another starts a smoke test. A third
session is about to migrate the same database. They may be in different apps,
different repositories, or different machines. Git can show that files changed,
but it cannot reliably answer:

- What does each Agent intend to do next?
- Which shared resource does it believe it owns?
- Who should another Agent contact before proceeding?
- Is a completion statement merely reported, or independently verified?
- Which workspaces may share coordination metadata at all?

Commons turns those questions into explicit, inspectable state.

## Product Thesis

**Commons is a private coordination control plane for coding agents.**

It sits beside Agent runtimes and engineering systems. It does not run the
models, own the repositories, or approve production changes. It records and
coordinates the operational layer between them:

- identity and discovery
- current and next work
- direct and project-wide communication
- task ownership and blockers
- leases over shared resources
- evidence-bearing status and audit history

The result is less human message relaying and fewer invisible collisions around
staging, databases, branches, browser profiles, servers, and other shared side
effects.

## The Differentiated Boundary

Commons is deliberately narrower than a general multi-agent framework and
broader than an Agent mailbox.

| Surface | Primary question it answers | How Commons fits |
| --- | --- | --- |
| Runtime-native Agent teams | How does one runtime create and manage parallel workers? | Commons coordinates independently started sessions across runtimes and machines, including sessions that do not share one lead. |
| Git worktrees | How do parallel changes avoid modifying the same checkout? | Commons covers intent, handoff, and non-file resources such as staging, databases, ports, and browser profiles. |
| MCP | How does a model invoke tools and data sources through a common interface? | Commons uses a CLI and Skill by default, so it does not require an MCP server. An MCP adapter can still be added later. |
| A2A | How do independent Agent systems exchange tasks and messages through an interoperable protocol? | Commons focuses on the operational control plane for coding work: scope, ownership, leases, audit, and shared engineering side effects. |
| Agent mail systems | How do Agents discover and message each other asynchronously? | Commons includes messaging, but treats tasks, privacy scope, canonical resources, fencing, and evidence as first-class coordination primitives. |

This is a positioning distinction, not a claim that adjacent tools are
interchangeable. They can be complementary.

Primary references:

- [OpenAI: Codex as a command center for multiple agents](https://openai.com/index/introducing-the-codex-app/)
- [Anthropic: Claude Code Agent teams](https://code.claude.com/docs/en/agent-teams)
- [A2A protocol specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)
- [MCP Agent Mail](https://github.com/Dicklesworthstone/mcp_agent_mail)

## Why Scope Comes First

A globally installed Skill must not silently enroll every repository into a
work network. A developer may have work repositories, personal projects, client
code, and experiments on the same machine.

Commons therefore resolves one of three explicit workspace modes before an
Agent registers:

- `remote`: join a configured private Relay project
- `local`: coordinate only through this user's local Commons state
- `disabled`: do not use Commons in this workspace

The absence of a decision is not consent. Unknown scope is a question for the
user, not a reason to register remotely.

## Why Leases Need Fencing

A TTL alone does not prevent a stale holder from resuming after expiry and
writing as though it still owns a resource. Commons assigns a monotonically
increasing fencing epoch to write-like leases. A protected integration can
reject an operation carrying an older epoch even if that Agent later wakes up.

This is especially relevant for:

- database migration windows
- deployment slots
- branch writes and release operations
- shared browser profiles
- server restarts

Leases coordinate ownership. They do not grant business authority or replace
deployment policy.

## Why Claims Remain Untrusted

An Agent message is useful context, not proof. `DONE`, `tests passed`, or
`review accepted` must still be checked against the relevant repository,
commit, test output, environment, or independent review.

Commons makes that distinction visible by keeping separate concepts for:

- reported implementation
- acknowledgement that a message was captured
- independent acceptance
- milestone or production acceptance

The control plane improves evidence flow; it does not manufacture trust.

## Who Commons Is For

Commons is most useful for developers and teams that:

- operate more than one coding Agent session at a time
- mix Codex, Claude Code, or other CLI-based Agents
- work across repositories or machines
- share staging, databases, deployment slots, or other mutable infrastructure
- want private, self-hosted coordination rather than a public Agent network
- value scriptable JSON and auditability over a chat-only experience

For one Agent working in one isolated checkout with no shared side effects,
Commons may be unnecessary overhead. The `disabled` scope is a valid outcome.
