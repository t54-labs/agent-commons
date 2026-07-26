# Commons Demo and Recording Script

## Demo Goal

Show one compelling fact before explaining architecture:

> Commons prevents two independently started coding Agents from silently
> performing conflicting work on the same shared resource.

Use only fixture infrastructure. Never record the T54 Labs production Relay,
real tokens, private repositories, customer data, browser profiles, or server
addresses.

## Recording Setup

From the Commons repository:

```bash
./scripts/install.sh --source .
cd examples/multi-agent-demo
./scripts/reset_demo.sh
```

Arrange the screen:

- left: Codex session running Agent A
- center: Claude Code session running Agent B
- right: `./scripts/show_state.sh watch`
- optional browser scene: fixture-backed Commons Console

Use a 16:9 canvas at 1440p or 1080p. Keep terminal font large enough to read
`deploy-slot`, the denial, the holder, and the direct message. Hide menu-bar
accounts, shell history, home-directory paths, notifications, and unrelated
tabs.

## 30-Second Hook

### 0:00-0:04

On-screen text:

> Codex is deploying staging.

Show Agent A acquire `deploy-slot:commons-demo/staging` and begin the simulated
45-second deploy.

### 0:04-0:09

On-screen text:

> Claude Code starts a smoke test.

Show Agent B attempt the same exclusive resource through Commons.

### 0:09-0:14

Freeze on the denial and holder ID.

On-screen text:

> The overlap is blocked before the command runs.

### 0:14-0:21

Show Agent B discover the holder and send a direct handoff request. Show the
message appear in the monitor or Console.

### 0:21-0:27

Show Agent A publish completion evidence and release. Show Agent B acquire and
run smoke.

### 0:27-0:30

End frame:

> Commons
> The shared control plane for coding Agents.
> Private. Self-hosted. No MCP required.

## 90-Second Product Demo

### Scene 1: The Invisible Conflict

Narration:

> These are separate Codex and Claude Code sessions. They do not share a lead or
> a context window, but they do share staging.

Show each Agent's handle, task, and plan.

### Scene 2: Ownership Before Side Effects

Narration:

> Codex announces its next step and acquires an exclusive lease over the
> deployment slot. The lease has a TTL and fencing epoch.

Show the active lease in the monitor.

### Scene 3: Denial Is the Feature

Narration:

> Claude tries to smoke the same environment. Commons denies the command before
> the script begins and returns the current holder.

Do not edit out the denial. It is the product proof.

### Scene 4: Agent-to-Agent Handoff

Narration:

> Claude messages the holder directly instead of asking a human to relay status.

Show the direct message and the current task steps.

### Scene 5: Evidence and Next Epoch

Narration:

> Codex publishes evidence and releases. Claude then acquires the next fenced
> lease and runs smoke against a stable environment.

Show the final audit sequence.

### Scene 6: Product Boundary

Narration:

> Commons does not spawn either Agent. It coordinates the engineering world
> they share: plans, messages, tasks, leases, and audit across sessions and
> machines.

Show the sanitized Console overview.

## Five-Minute Technical Walkthrough

### 1. Installation and Scope

```bash
./scripts/install.sh --source .
commons scope resolve --workspace "$PWD" --json
```

Explain that the globally installed Skill does not enroll every workspace. Show
`remote`, `local`, and `disabled` as explicit choices.

### 2. Deterministic Proof

```bash
make demo
```

Explain the six scenarios and that they use an isolated `COMMONS_HOME` with no
real infrastructure.

### 3. Private Relay

```bash
export COMMONS_RELAY_TOKEN="<generated-test-token>"
export COMMONS_WORKSPACE_NAME="Demo Team"
docker compose up --build -d
```

Do not reveal the token on screen. Open the Console after authentication and
show Projects, Active/Registered Agents, tasks, broadcasts, direct messages,
leases, and activity.

### 4. Resource Model

Show these examples:

```text
deploy-slot:example-app/staging
db:example-app/staging
git-branch:example-app/main
browser-profile:chrome/release
```

Explain canonicalization, compatibility modes, TTL, holder ownership, and
fencing epochs. State clearly that strong enforcement requires wrappers or an
integration checking the lease.

### 5. Evidence Model

Show a task with current step, next step, progress, and a completion broadcast.
Explain that acknowledgement is not approval and Agent prose remains untrusted.

## Exact Agent Prompts

Use the repository prompts rather than improvising:

- `prompts/agent-a-deployer.md`
- `prompts/agent-b-smoke-runner.md`
- `prompts/agent-c-db-migrator.md`
- `prompts/agent-d-db-reader.md`
- `prompts/agent-e-release-manager.md`
- `prompts/agent-f-security-reviewer.md`

The first recording should use only Agents A and B. Add C through F for the
long technical walkthrough.

## Capture Checklist

- [ ] Fixture or demo data only
- [ ] No token visible in command, environment, clipboard, or browser
- [ ] No personal home path or shell prompt username
- [ ] No production hostname, IP address, project, Agent, or message
- [ ] Denial occurs before the simulated side-effect script starts
- [ ] Direct message visibly reaches the intended holder
- [ ] Release and next fencing epoch are visible
- [ ] Final Console view shows only sanitized fixture projects
- [ ] Captions define Commons as a control plane, not an Agent launcher
- [ ] Audio and captions state the self-hosted private Relay boundary

## Editing Guidance

- Keep the first cut under 30 seconds and the technical cut under five minutes.
- Use hard cuts and readable zooms; avoid decorative motion that obscures state.
- Caption the resource ID, denial, holder, release, and next acquisition.
- Do not speed up terminal output beyond readability.
- End on the product and repository, not a generic AI animation.
- Include the exact commit used for the recording in the video description.
