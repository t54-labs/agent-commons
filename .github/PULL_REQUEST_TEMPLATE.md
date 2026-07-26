## Problem

What coordination problem does this change solve?

## Change

Describe the behavioral surface and important implementation decisions.

## Evidence

- [ ] `make test-python`
- [ ] `make docs-check`
- [ ] `npm --prefix web run build` when Console code changes
- [ ] `npm --prefix web run test:e2e` when Console behavior changes
- [ ] Docker or real-runtime checks when deployment or Skill behavior changes

List exact commands, results, and explicit `NOT RUN` gates.

## Security and Privacy

- [ ] No tokens, credentials, private prompts, raw transcripts, customer data, or personal absolute paths were added.
- [ ] Workspace scope and private Relay boundaries remain explicit.
- [ ] New message content is treated as untrusted input.
- [ ] Lease or fencing behavior has regression coverage when changed.

## Compatibility

Call out CLI/JSON, database migration, Skill, Relay, and Console compatibility.

## AI-Assisted Work

Name any coding Agent used materially and confirm that the submitter reviewed
the diff and owns its correctness. Agent-generated claims are not a substitute
for the evidence above.
