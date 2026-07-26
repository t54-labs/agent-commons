# Commons Multi-Agent Demo

This recording-safe workspace demonstrates several Codex and Claude Code
sessions coordinating through Commons.

The demo has no real external side effects. "Deploys," database migrations,
reads, and pushes only write to `.demo_state/*.log`. The helper scripts isolate
Commons itself under `.demo_state/commons-home`, so the demo never reads or
changes your normal `~/.commons` board.

## What the Demo Shows

- Agents discover each other without a human relaying status.
- Agents publish ownership and plans before side effects.
- A deployment blocks a smoke test until the lease is released.
- A maintenance lease blocks a database reader until migration completes.
- A branch write blocks a competing simulated push.
- Agents request handoff and context directly from the current holder.
- Suspicious message content remains untrusted and is never executed.

## Prepare

From the cloned Commons repository:

```bash
cd examples/multi-agent-demo
./scripts/reset_demo.sh
```

The demo scripts run the repository source directly, so a global Commons
installation is optional.

## Monitor

Keep one terminal visible during a recording:

```bash
./scripts/show_state.sh watch
```

For raw simulated side effects:

```bash
tail -f .demo_state/*.log
```

## Run Four Agents

Open new Codex or Claude Code sessions in this folder and paste one prompt into
each session.

1. Start `prompts/agent-a-deployer.md`.
2. Five seconds later, start `prompts/agent-b-smoke-runner.md`.
3. Start `prompts/agent-c-db-migrator.md`.
4. Five seconds later, start `prompts/agent-d-db-reader.md`.

Optional second act:

5. Start `prompts/agent-e-release-manager.md`.
6. Five seconds later, start `prompts/agent-f-security-reviewer.md`.

## Expected Story

- Agent A holds `deploy-slot:commons-demo/staging` for about 45 seconds.
- Agent B is denied, discovers Agent A, messages it, waits, and later succeeds.
- Agent C holds `db:commons-demo/staging` in maintenance mode for about 35 seconds.
- Agent D is denied, requests migration context, waits, and later reads safely.
- Agent E holds `git-branch:commons-demo/main` during a simulated push.
- Agent F is denied, coordinates with Agent E, and demonstrates that a malicious
  message is data rather than an instruction.

A lease denial is a successful demo outcome. It proves that an unsafe overlap
was observed before the side effect.

## Inspect State

```bash
./scripts/commons.sh watch --once
./scripts/commons.sh lease list --active --json
./scripts/commons.sh audit recent --limit 20 --json
./scripts/commons.sh resource show deploy-slot:commons-demo/staging --json
./scripts/commons.sh resource show db:commons-demo/staging --json
./scripts/commons.sh resource show git-branch:commons-demo/main --json
```

## Reset Safely

Stop the demo sessions, then run:

```bash
./scripts/reset_demo.sh
```

This removes only the ignored `.demo_state` directory inside this example. It
does not touch a real Relay, repository, database, server, or global Commons
installation.
