# Agent D: Database Reader

You are the read-only database validation agent in the Commons multi-agent demo.
Start this about 5 seconds after Agent C.

Run from:

```bash
cd "$(git rev-parse --show-toplevel)/examples/multi-agent-demo"
```

Do the following:

1. Run `./scripts/commons.sh doctor --fix --json`.
2. Register and set shell variables:

```bash
eval "$(./scripts/register_agent.sh demo-db-reader auto "Demo D: database read validation")"
```

3. Publish this plan:

```bash
./scripts/commons.sh plan publish --task "$TASK_ID" --agent "$AGENT_ID" --summary "Attempt a read lease on db:commons-demo/staging. If maintenance is active, request context from the holder and wait."
```

4. Try the read command through Commons. It is expected to be denied while
   Agent C is migrating:

```bash
./scripts/commons.sh --json run --resource db:commons-demo/staging --mode read --agent "$AGENT_ID" --ttl 1m --reason "Read DB snapshot after migration" -- ./scripts/read_db_snapshot.sh "$AGENT_ID"
```

5. If denied, inspect conflicts:

```bash
./scripts/commons.sh lease conflicts db:commons-demo/staging --mode read --json
./scripts/commons.sh lease list --active --json
```

6. Request context from the holder shown in the denial or active lease:

```bash
HOLDER_AGENT_ID="$(./scripts/holder_from_conflict.sh db:commons-demo/staging read)"
./scripts/commons.sh context request @"$HOLDER_AGENT_ID" --sender "$AGENT_ID" --task "$TASK_ID" --reason "Need migration version and validation evidence before DB read validation."
```

7. Wait until the maintenance lease disappears, then retry the read command from
   step 4. Do not bypass Commons.

8. When it succeeds, publish context and complete:

```bash
./scripts/commons.sh context publish --task "$TASK_ID" --agent "$AGENT_ID" --summary "DB read validation completed after migration lease released. Evidence: .demo_state/read.log."
./scripts/commons.sh task complete "$TASK_ID" --summary "DB read validation completed after Commons coordination."
```
