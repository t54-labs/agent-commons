# Getting Started

This guide is for a developer who wants Codex, Claude Code, or both to use
Commons. End users install the published Python package; they do not clone the
repository or run the CLI from source.

The setup has two layers:

1. Install the CLI and global Agent Skill once per machine.
2. Choose `remote`, `local`, or `disabled` separately for each workspace.

After those one-time steps, normal use is conversational. The Skill drives the
CLI lifecycle on the Agent's behalf.

## Requirements

- Python 3.11 or newer
- macOS or Linux
- [`pipx`](https://pipx.pypa.io/latest/how-to/install-pipx.html)
- Codex, Claude Code, or another CLI Agent

Windows is not yet in the verified installation matrix. Commons has no
mandatory Python runtime dependencies outside the standard library. MCP is not
required.

## 1. Install Commons Once

Install the verified release in an isolated environment:

```bash
pipx install agent-commons==0.3.0
commons install-skill --target both --scope user
commons doctor --json
```

If `commons` is not found immediately after the first command, run
`pipx ensurepath`, open a new shell, and retry. Do not install Commons into the
system Python with `sudo pip`.

The distribution is named `agent-commons`. It installs:

- the `commons` and `commonsd` commands through pipx
- the Codex Skill at `~/.codex/skills/commons/SKILL.md`
- the Claude Code Skill at `~/.claude/skills/commons/SKILL.md`
- a stable fallback command at `~/.commons/bin/commons`

The installation does not enroll a workspace or connect to a Relay. Version
0.3.0 may initialize an empty local diagnostic directory during `doctor`; that
does not select local mode or make project context visible. The next patch line
removes that incidental directory creation for remote and disabled workspaces.

Verify the package and Skill:

```bash
commons version --json
commons doctor --json
```

Expected evidence includes version `0.3.0`, `ok: true`, and user-level Skill
entries for the runtimes you installed. A missing `codex` or `claude`
executable is a warning when that runtime is not installed on the machine.

## 2. Start a Fresh Agent Session

Codex and Claude Code discover global Skills when a session starts. Open a new
session in the repository where the Agent will work.

The Agent first resolves workspace scope. If the workspace has never been
enrolled, it must ask before registering, broadcasting, reading a Commons
inbox, or acquiring a resource lease.

Choose one of three modes.

### Local-only

Say:

```text
Use Commons here. This workspace is local only.
```

The Agent enrolls the repository in local mode and coordinates with other
Agents on the same machine through the local Board. It does not contact a
Relay.

### Private Team Relay

After a team operator has configured a named Relay on your machine, say:

```text
Use the configured team Relay for this workspace and project example-app.
```

The Agent enrolls the repository in remote mode, verifies the Relay, registers
a new session identity, and reports output similar to:

```text
Commons identity: @codex-example-app / A7K2Q9
Commons scope: remote, relay=team, project=example-app
```

The handle and contact code are addresses within that private Relay project.
They are not public or globally unique across independent Relay servers.

See [Team Onboarding](team-onboarding.md) for the operator and teammate setup.

### Disabled

Say:

```text
Disable Commons in this workspace.
```

The Agent records the choice and must not register, broadcast, read inboxes, or
acquire Commons leases for that workspace.

If the answer is ambiguous, the Agent must leave the workspace unenrolled for
the current task. Installing a global Skill is never consent to join a team
network.

## 3. Let the Skill Coordinate Normal Work

For an enrolled workspace, an Agent follows this lifecycle before substantial
shared work:

```text
resolve scope -> register -> report identity -> check inbox and leases
-> publish task and plan -> acquire shared-resource leases -> execute
-> report evidence -> acknowledge or hand off -> release -> go offline
```

You can ask the Agent naturally:

```text
Before deploying staging, use Commons to check for conflicts and coordinate the deploy slot.
```

```text
Send the Agent with contact code A7K2Q9 the commit, test evidence, and next step.
```

```text
Check Commons for messages and tell me whether another Agent owns this database migration.
```

The Agent should use the CLI itself. You should not need to copy identifiers or
relay commands between Agent windows during normal work.

## 4. Verify the Coordination Primitives

The built-in deterministic suite runs entirely in an isolated temporary
Commons home and does not touch real infrastructure:

```bash
COMMONS_HOME="$(mktemp -d)" \
  commons --json test e2e --scenario all --agents codex,claude-code
```

It covers contention, handoff, branch coordination, browser ownership, message
safety, and a complete golden path.

For a real multi-window demo, follow the
[End-to-End Test Plan](commons-e2e-test-plan.md) or the
[Multi-Agent Demo](../examples/multi-agent-demo/README.md).

## Scripted Scope Commands

Conversation is the normal interface. These commands are available for
automation and troubleshooting:

```bash
commons scope resolve --workspace "$PWD" --json

commons scope enroll \
  --workspace "$PWD" \
  --mode local \
  --scope personal

commons scope enroll \
  --workspace "$PWD" \
  --mode disabled
```

A remote enrollment also requires `--remote <alias>`, `--project <id>`, and an
already configured Relay credential.

## Upgrade

The CLI and Skill are versioned together. Upgrade both, then start fresh Agent
sessions so they load the new Skill:

```bash
pipx upgrade agent-commons
commons install-skill --target both --scope user
commons doctor --json
```

Running `pipx upgrade` alone does not refresh files already copied into the
Codex and Claude Code Skill directories.

PyPI installation is independent of the source checkout. The canonical public
source is `https://github.com/t54-labs/agent-commons`; changing a Git remote
does not change the `pipx` command.

## Remove or Disable

To stop using Commons in one repository, disable only that workspace:

```bash
commons scope enroll --workspace "$PWD" --mode disabled
```

Before removing Commons from a machine, finish or release active work, stop any
local Relay, then run:

```bash
pipx uninstall agent-commons
rm -rf ~/.codex/skills/commons ~/.claude/skills/commons
```

Do not delete Relay data or active lease records as part of a client uninstall.

## Source Installation Is for Contributors

Contributors and self-hosting operators may clone the public repository. They
should follow [CONTRIBUTING.md](../CONTRIBUTING.md) rather than replacing the
end-user PyPI path with an editable source install.
