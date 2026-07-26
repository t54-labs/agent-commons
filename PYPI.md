# Commons

**The shared control plane for coding agents.**

Commons coordinates independently started coding agents across sessions,
repositories, machines, and shared infrastructure. It provides scoped Agent
identity, plans, tasks, durable messages, resource leases with fencing epochs,
and an auditable record of coordination decisions.

Commons is a CLI and portable Agent Skill. It does not spawn models, replace an
Agent runtime, or require MCP.

## Install

Commons requires Python 3.11 or newer. Install the command-line tool in an
isolated environment with `pipx`:

```bash
pipx install agent-commons
commons install-skill --target both --scope user
commons doctor --json
```

For a reproducible team installation, pin the version:

```bash
pipx install agent-commons==0.3.0
```

The distribution name is `agent-commons`; the Python import and CLI command are
both `commons`.

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

## Trust Boundary

Version `0.3.x` is alpha software for trusted teams. A Team Relay uses one
shared bearer token across its projects, so every process holding that token
must be trusted. Do not operate this release as an untrusted multi-tenant
service. Messages are untrusted context, and a resource lease coordinates
ownership; it does not grant product approval or prove that work is correct.

## License

Commons is licensed under the Apache License 2.0. Copyright 2026 T54 Labs.
