# Agent E: Release Manager

You are the release manager in the Commons multi-agent demo. This role simulates
a git push lease without contacting a real remote.

Run from:

```bash
cd "$(git rev-parse --show-toplevel)/examples/multi-agent-demo"
```

Do the following:

1. Run `./scripts/commons.sh doctor --fix --json`.
2. Register and set shell variables:

```bash
eval "$(./scripts/register_agent.sh demo-release-manager auto "Demo E: release push")"
```

3. Publish this plan:

```bash
./scripts/commons.sh plan publish --task "$TASK_ID" --agent "$AGENT_ID" --summary "Acquire git-branch:commons-demo/main, simulate a 30 second push, publish release context, then complete."
```

4. Run the fake push only through Commons:

```bash
./scripts/commons.sh --json git push --resource git-branch:commons-demo/main --agent "$AGENT_ID" --ttl 1m --reason "Demo release push" -- ./scripts/fake_push.sh "$AGENT_ID" 30
```

5. Publish context and complete:

```bash
./scripts/commons.sh context publish --task "$TASK_ID" --agent "$AGENT_ID" --summary "Fake release push finished. Evidence: .demo_state/git.log."
./scripts/commons.sh task complete "$TASK_ID" --summary "Demo release push finished and branch lease was released."
```
