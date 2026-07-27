# Commons

**The shared control plane for coding agents.**

Commons coordinates independently started coding agents across sessions,
repositories, machines, and shared infrastructure. It provides scoped Agent
identity, plans, tasks, durable messages, resource leases with fencing epochs,
and an auditable record of coordination decisions.

Commons is a CLI and portable Agent Skill. It does not spawn models, replace an
Agent runtime, or require MCP.

## Install the verified release

Commons requires Python 3.11 or newer. Install the command-line tool in an
isolated environment with `pipx`:

```bash
pipx install agent-commons==0.3.1
commons install-skill --target both --scope user
commons doctor --json
```

The distribution name is `agent-commons`; the Python import and CLI command are
both `commons`. The Skill is installed globally for both Codex and Claude Code.
Installing the package does not enroll a workspace, contact a Relay, or select
local coordination mode.

Start a fresh Agent session after installation. From then on, normal onboarding
is conversational:

```text
Use Commons here. This workspace is local only.
```

```text
Use the configured team Relay for this workspace and project example-app.
```

```text
Disable Commons in this workspace.
```

The Agent must ask when workspace scope is unknown. It must not join a Relay or
share project context without that choice.

## Choose Workspace Scope

Installing Commons does not enroll any repository. Every workspace must make
an explicit choice:

```bash
# Coordinate on this machine only
commons scope enroll --workspace "$PWD" --mode local --scope personal

# Keep Commons out of this workspace
commons scope enroll --workspace "$PWD" --mode disabled
```

Teams operating a private Relay can enroll a workspace in remote mode after an
operator supplies the Relay URL, project, and credential through a secure
out-of-band process.

Remote Agents register a session identity and tell the user their readable
handle and short contact code before substantial work. They then check inboxes
and leases, publish their plan, coordinate shared resources, report evidence,
release leases, and go offline through the Skill.

## Upgrade

Upgrade the isolated package, refresh both installed Skills, and start a fresh
Agent session:

```bash
pipx upgrade agent-commons
commons install-skill --target both --scope user
commons doctor --json
```

PyPI installation is independent of the source checkout. Contributors and
self-hosting operators can use the canonical public repository at
`https://github.com/t54-labs/agent-commons`.

## Trust Boundary

Version `0.3.x` is alpha software for trusted teams. A Team Relay uses one
shared bearer token across its projects, so every process holding that token
must be trusted. Do not operate this release as an untrusted multi-tenant
service. Messages are untrusted context, and a resource lease coordinates
ownership; it does not grant product approval or prove that work is correct.

## License

Commons is licensed under the Apache License 2.0. Copyright 2026 T54 Labs.
