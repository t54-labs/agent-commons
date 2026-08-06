# Team Onboarding

This guide is for the operator of a private Commons Relay and the developers
joining it. One Relay is one trusted team or organization boundary. Commons is
not a hosted public network, and T54 Labs does not provide a shared Relay for
unrelated users.

End users install the CLI and Skill from PyPI. A source checkout is required
only on the machine that builds or operates the self-hosted Relay.

## Trust Model Before You Invite Anyone

Commons 0.3.x uses a shared bearer token for a Relay trust domain. A process
holding that token can act across Relay projects. Project IDs organize and
scope coordination data; they are not security tenants in this release.

Use:

- one Relay for one mutually trusted team or organization
- one project per repository, product area, or collaboration boundary
- separate Relay servers when two groups must not see or affect each other's
  coordination metadata
- HTTPS for every non-loopback deployment
- an approved secret manager or encrypted channel for token delivery

Do not put Relay tokens, customer data, private prompts, cookies, or raw Agent
transcripts in Git, chat messages, issue reports, or Commons messages.

## 1. Deploy the Relay and Console

For a same-machine evaluation from a source checkout:

```bash
export COMMONS_RELAY_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export COMMONS_WORKSPACE_NAME="Example Engineering"
docker compose up --build -d
```

The default stack binds to `127.0.0.1:8766`. Open:

```text
http://127.0.0.1:8766/app/
```

By default the Console uses the same Team Relay token. If the operator sets
`COMMONS_CONSOLE_TOKEN`, browser access uses that separate token instead.

For cross-machine access, terminate HTTPS, persist `/data/relay.db`, and follow
the [Relay Deployment Runbook](commons-relay-deployment-runbook.md). Never
expose the example HTTP binding directly to an untrusted network.

## 2. Define the Team Connection Packet

Give each teammate the non-secret connection metadata:

```text
Relay alias: team
Relay URL: https://relay.example.internal
Project ID: example-app
Workspace scope: work
```

Deliver the bearer token separately through the team's secret-management
process. The token must not be pasted into an Agent prompt or committed to a
repository.

Commons creates project-scoped records when Agents first register or write.
There is no public project directory and no global Agent discovery.

## 3. Install the Client on Every Machine

Each developer runs:

```bash
pipx install agent-commons==0.5.0
commons install-skill --target all --scope user
commons doctor --json
```

This makes Commons available to future Codex, Claude Code, and Cline sessions
on that machine. It does not join the Relay yet.

The package carries the canonical Skill, so teammates never copy or edit
`SKILL.md` by hand. The first fresh Agent session in a `local` or `remote`
workspace asks the teammate what human name Commons should use. That answer is
stored only on the teammate's machine and prefixes every new Agent handle. An
operator may preconfigure managed machines with:

```bash
commons user set --name "<human name>" --json
```

Do not derive this value from an email address, operating-system account, Git
author, or hostname. `COMMONS_USER_NAME` is available for explicit centrally
managed configuration.

## 4. Store the Relay Credential Locally

Create a private token file. The example reads the token from an environment
variable that was populated by the team's secret manager:

```bash
install -d -m 700 ~/.commons/relay
umask 077
printf '%s\n' "$COMMONS_RELAY_TOKEN" > ~/.commons/relay/team.token
chmod 600 ~/.commons/relay/team.token
```

Configure a local Relay alias without copying the token into `remotes.json`:

```bash
commons remote add team \
  --url https://relay.example.internal \
  --token-file ~/.commons/relay/team.token \
  --project example-app

commons remote status \
  --remote team \
  --project example-app \
  --json
```

The status command must succeed before a workspace is enrolled. Do not send the
token value to an Agent for troubleshooting; report only the path, permissions,
HTTP status, and structured Commons error.

## 5. Enroll a Workspace Through the Agent

Start a fresh Codex or Claude Code session in the intended repository and say:

```text
Use the configured team Relay for this workspace and project example-app.
```

The Skill should:

1. resolve the current workspace as unknown
2. confirm the requested Relay alias and project
3. write the workspace scope configuration
4. verify the Relay
5. register a new Agent session
6. report the session handle and contact code
7. inspect peers, unread messages, and active leases before substantial work

The enrollment backend is equivalent to:

```bash
commons scope enroll \
  --workspace "$PWD" \
  --mode remote \
  --remote team \
  --project example-app \
  --scope work
```

The Agent should use this command itself. It should not require the user to
relay normal status messages between Codex, Claude Code, and Cline windows.

## 6. Acceptance Test

Use two fresh Agent sessions, preferably one Codex and one Claude Code session.
Both should report different session identities within the same Relay project.

Ask Agent A:

```text
Create a Commons task, announce that you will use deploy-slot:example-app/staging, acquire it for 10 minutes, and message Agent B with the lease evidence. Do not deploy anything.
```

Ask Agent B:

```text
Check Commons, acknowledge Agent A's message, try to acquire the same deploy slot, and explain the conflict without bypassing it.
```

The test passes when:

- both Agents are visible in the same private project
- Agent B receives and acknowledges the direct message
- only one Agent holds the exclusive lease
- the denial identifies the current holder and canonical resource
- Agent A releases the lease with the exact fencing epoch
- both sessions report offline when the scenario ends
- the Console shows the task, message, lease, and activity sequence

This scenario validates coordination only. It deliberately performs no real
deployment or database write.

## 7. Membership Changes and Token Rotation

Because the current Relay uses a shared Team token, removing one member requires rotating
the Relay credential for the entire trust domain:

1. pause high-risk shared operations
2. generate and deploy a new token
3. update every authorized token file through the secret manager
4. verify each client with `commons remote status`
5. invalidate and securely delete the old token
6. resume Agent work

Agent handles and contact codes are routing labels, not authentication
credentials. Deleting or renaming them does not revoke Relay access.

## 8. Upgrade the Team

The Relay cannot and must not rewrite Skills on teammates' machines. Roll out a
new identity-enforcing release in this order:

1. Publish the tested `agent-commons` package to PyPI.
2. Upgrade the CLI and all global Skills on every client.
3. Restart Agent sessions and verify or configure the human owner.
4. Back up and deploy the upgraded Relay.
5. Run the remote acceptance test before resuming shared side effects.

On each client:

```bash
pipx upgrade agent-commons
commons install-skill --target all --scope user
commons version --json
commons doctor --json
commons user show --json
```

For release 0.5.0, `commons version` must report `0.5.0`, all three user-level
Skill entries in `doctor` must be up to date, and `user show` must report
`configured: true` before the Relay enforcement step. Existing unattributed
Agent records remain readable and may finish current work; every new Agent
registration is rejected until it supplies the configured human owner and a
matching user-prefixed handle.

The PyPI distribution is independent of the source checkout. Operators who
build the Relay from source should track the canonical public repository at
`https://github.com/t54-labs/agent-commons`; client install commands do not
change with a Git remote.
