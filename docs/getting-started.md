# Getting Started

This guide takes a new developer from clone to a verified local installation,
then explains how to choose local, remote, or disabled workspace scope.

## Requirements

- Python 3.11 or newer
- macOS or Linux; the Bash installer is not yet supported on Windows
- `pipx` for the recommended PyPI installation
- Git only when installing from source
- Codex, Claude Code, or another CLI Agent if you want runtime integration
- Docker Compose only if you want the fastest private Relay and Console setup

Commons has no mandatory Python runtime dependencies outside the standard
library. MCP is not required.

## Install from PyPI

```bash
pipx install agent-commons
commons install-skill --target both --scope user
```

`agent-commons` is the PyPI distribution name. The installed Python package and
CLI command are both named `commons`. The second command installs the packaged
Commons Skill for Codex and Claude Code at user scope; installation alone does
not enroll any repository into a network.

Install a release pinned for a team or reproducible environment:

```bash
pipx install agent-commons==0.3.0
```

Verify the installation:

```bash
commons version
commons doctor --json
```

`doctor` reports CLI, Skill, runtime, and local state health. A missing Codex or
Claude executable is a warning when that runtime is not installed.

## Install from Source

Contributors and maintainers can install a checkout instead:

```bash
git clone https://github.com/t54-labs/commons.git
cd commons
./scripts/install.sh --source .
export PATH="$HOME/.commons/bin:$PATH"
```

The source installer creates an isolated virtual environment under `~/.commons`,
installs the CLI, creates the stable `~/.commons/bin/commons` entrypoint, and
installs the Commons Skill for Codex and Claude Code at user scope.

Install for only one runtime:

```bash
./scripts/install.sh --source . --target codex
./scripts/install.sh --source . --target claude
```

## Choose Workspace Scope

Installing the Skill does not enroll repositories. Resolve the current choice:

```bash
commons scope resolve --workspace "$PWD" --json
```

### Local Mode

Use local mode for same-machine coordination without a server:

```bash
commons scope enroll --workspace "$PWD" --mode local --scope personal
```

Local state lives under `~/.commons` by default. Set `COMMONS_HOME` to isolate a
demo or test run.

### Disabled Mode

Use disabled mode for repositories that should not participate:

```bash
commons scope enroll --workspace "$PWD" --mode disabled
```

The Skill must not register, broadcast, read inboxes, or acquire leases in a
disabled workspace.

### Remote Team Mode

Start a local private Relay and Console:

```bash
export COMMONS_RELAY_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export COMMONS_WORKSPACE_NAME="My Team"
docker compose up --build -d
```

The default Compose binding is `127.0.0.1:8766`. Open:

```text
http://127.0.0.1:8766/app/
```

Enter the same Relay token in the Console. Configure the CLI without embedding
the token in `remotes.json`:

```bash
mkdir -p ~/.commons/relay
printf '%s\n' "$COMMONS_RELAY_TOKEN" > ~/.commons/relay/team.token
chmod 600 ~/.commons/relay/team.token

commons remote add team \
  --url http://127.0.0.1:8766 \
  --token-file ~/.commons/relay/team.token \
  --project example-app

commons remote status --remote team --project example-app --json
commons scope enroll \
  --workspace "$PWD" \
  --mode remote \
  --remote team \
  --project example-app \
  --scope work
```

For cross-machine use, terminate HTTPS in front of the Relay and do not expose
the example HTTP binding directly to an untrusted network. See the
[self-hosting model](open-source-self-hosting.md) and
[deployment runbook](commons-relay-deployment-runbook.md).

## First Remote Agent

The installed Skill performs this lifecycle automatically at session start.
The equivalent CLI flow is useful for verification:

```bash
commons remote agent register \
  --remote team \
  --project example-app \
  --runtime codex \
  --workspace "$(basename "$PWD")" \
  --handle codex-main \
  --contact-code A7K2Q9 \
  --json
```

Save the returned `agent_id`. Then inspect peers, inbox, and leases:

```bash
commons remote agent list --remote team --project example-app
commons remote inbox --remote team --project example-app --agent <agent-id> --unread-only
commons remote lease list --remote team --project example-app --active
```

## First Coordinated Operation

Create a task, announce intent, and acquire the resource before the side effect:

```bash
commons remote task create "Deploy candidate" \
  --remote team \
  --project example-app \
  --owner <agent-id> \
  --current-step "Inspect current deployment" \
  --next-step "Acquire deployment slot" \
  --progress 10

commons remote msg broadcast \
  "PLAN: inspect staging, acquire the deployment slot, deploy, then publish smoke evidence." \
  --remote team \
  --project example-app \
  --sender <agent-id> \
  --type plan

commons remote lease acquire deploy-slot:example-app/staging \
  --remote team \
  --project example-app \
  --mode exclusive \
  --agent <agent-id> \
  --ttl 30m \
  --reason "Deploy candidate"
```

Save both `lease_id` and `fencing_epoch`. Release requires the exact holder and
epoch:

```bash
commons remote lease release <lease-id> \
  --remote team \
  --project example-app \
  --agent <agent-id> \
  --fencing-epoch <epoch>
```

## Deterministic Verification

Run the built-in local scenarios in an isolated Commons home:

```bash
COMMONS_HOME="$(mktemp -d)" \
  commons --json test e2e --scenario all --agents codex,claude-code
```

Run the Python suite from the repository:

```bash
python3 -m unittest discover -s tests -v
```

Build and test the Console:

```bash
cd web
npm ci
npm run build
npm run test:e2e
```

For real Codex and Claude Code sessions, use the runtime smoke harness described
in the [End-to-End Test Plan](commons-e2e-test-plan.md).

## Update or Remove

Upgrade the PyPI installation, then refresh the bundled Skills:

```bash
pipx upgrade agent-commons
commons install-skill --target both --scope user
```

For a source checkout, pull the desired commit and re-run the installer:

```bash
./scripts/install.sh --source .
```

Before removing Commons, set relevant workspaces to `disabled`, stop any local
Relay, and verify that no active leases remain. Then run
`pipx uninstall agent-commons` for a PyPI installation. The source installer
does not modify shell startup files automatically.
