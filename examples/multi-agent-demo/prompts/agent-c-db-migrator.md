# Agent C: Database Migrator

You are the database migration holder in the Commons multi-agent demo.

Run from:

```bash
cd "$(git rev-parse --show-toplevel)/examples/multi-agent-demo"
```

Do the following:

1. Run `./scripts/commons.sh doctor --fix --json`.
2. Register and set shell variables:

```bash
eval "$(./scripts/register_agent.sh demo-db-migrator auto "Demo C: database migration")"
```

3. Publish this plan:

```bash
./scripts/commons.sh plan publish --task "$TASK_ID" --agent "$AGENT_ID" --summary "Acquire db:commons-demo/staging in maintenance mode, simulate a 35 second migration, publish migration context, then complete."
```

4. Broadcast the maintenance window:

```bash
./scripts/commons.sh msg broadcast --sender "$AGENT_ID" --task "$TASK_ID" --resource db:commons-demo/staging "Starting demo DB migration; reads should wait for maintenance lease to release."
```

5. Run the migration only through Commons:

```bash
./scripts/commons.sh --json db migrate --resource db:commons-demo/staging --agent "$AGENT_ID" --ttl 2m --reason "Demo DB migration maintenance window" -- ./scripts/run_migration.sh "$AGENT_ID" 35
```

6. Publish context and complete:

```bash
./scripts/commons.sh context publish --task "$TASK_ID" --agent "$AGENT_ID" --summary "Migration 001_add_audit_log.sql applied in demo state. Evidence: .demo_state/migration.log and .demo_state/db_version.txt."
./scripts/commons.sh task complete "$TASK_ID" --summary "Demo DB migration finished and maintenance lease was released."
```

If Commons denies the lease, message the holder and wait.
