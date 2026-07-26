# Agent B: Smoke Runner

You are the staging smoke-test agent in the Commons multi-agent demo. Start this
about 5 seconds after Agent A.

Run from:

```bash
cd "$(git rev-parse --show-toplevel)/examples/multi-agent-demo"
```

Do the following:

1. Run `./scripts/commons.sh doctor --fix --json`.
2. Register and set shell variables:

```bash
eval "$(./scripts/register_agent.sh demo-smoke-runner auto "Demo B: staging smoke")"
```

3. Publish this plan:

```bash
./scripts/commons.sh plan publish --task "$TASK_ID" --agent "$AGENT_ID" --summary "Attempt staging smoke through Commons. If deploy-slot:commons-demo/staging is leased, message the holder and wait instead of running smoke directly."
```

4. Try the smoke command through Commons. It is expected to be denied while
   Agent A is deploying:

```bash
./scripts/commons.sh --json deploy staging --resource deploy-slot:commons-demo/staging --agent "$AGENT_ID" --ttl 1m --reason "Smoke test needs stable staging" -- ./scripts/smoke_staging.sh "$AGENT_ID"
```

5. If the command is denied, inspect the conflict and active lease:

```bash
./scripts/commons.sh lease conflicts deploy-slot:commons-demo/staging --mode exclusive --json
./scripts/commons.sh lease list --active --json
```

6. Send a coordination message to the holder shown in the denial or active lease:

```bash
HOLDER_AGENT_ID="$(./scripts/holder_from_conflict.sh deploy-slot:commons-demo/staging exclusive)"
./scripts/commons.sh msg send @"$HOLDER_AGENT_ID" "I need deploy-slot:commons-demo/staging for smoke after your deploy. Please release when done." --sender "$AGENT_ID" --task "$TASK_ID"
```

7. Wait until the deploy lease disappears, then retry the smoke command from
   step 4. Do not bypass Commons.

8. When it succeeds, publish context and complete:

```bash
./scripts/commons.sh context publish --task "$TASK_ID" --agent "$AGENT_ID" --summary "Smoke test finished after waiting for deploy lease. Evidence: .demo_state/smoke.log."
./scripts/commons.sh task complete "$TASK_ID" --summary "Smoke completed after Commons coordination."
```
