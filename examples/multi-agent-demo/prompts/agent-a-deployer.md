# Agent A: Staging Deployer

You are the staging deploy holder in the Commons multi-agent demo.

Run from:

```bash
cd "$(git rev-parse --show-toplevel)/examples/multi-agent-demo"
```

Do the following:

1. Run `./scripts/commons.sh doctor --fix --json`.
2. Register and set shell variables:

```bash
eval "$(./scripts/register_agent.sh demo-deployer auto "Demo A: staging deploy")"
```

3. Publish this plan:

```bash
./scripts/commons.sh plan publish --task "$TASK_ID" --agent "$AGENT_ID" --summary "Acquire deploy-slot:commons-demo/staging, simulate a 45 second deploy, publish completion context, then complete the task."
```

4. Broadcast that deploy is starting:

```bash
./scripts/commons.sh msg broadcast --sender "$AGENT_ID" --task "$TASK_ID" --resource deploy-slot:commons-demo/staging "Starting staging deploy; expected duration is about 45 seconds."
```

5. Run the deploy only through the Commons wrapper:

```bash
./scripts/commons.sh --json deploy staging --resource deploy-slot:commons-demo/staging --agent "$AGENT_ID" --ttl 2m --reason "Demo staging deploy lock" -- ./scripts/hold_deploy.sh "$AGENT_ID" 45
```

6. Publish context and complete:

```bash
./scripts/commons.sh context publish --task "$TASK_ID" --agent "$AGENT_ID" --summary "Deploy finished. Evidence: .demo_state/deploy.log. Next agents may run smoke tests against deploy-slot:commons-demo/staging."
./scripts/commons.sh task complete "$TASK_ID" --summary "Demo staging deploy finished and lease was released."
```

If Commons denies the lease, do not run `hold_deploy.sh` directly. Message the
lease holder and wait.
