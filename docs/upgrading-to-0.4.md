# Upgrading a Team to Commons 0.4

Commons 0.4 adds explicit human attribution to every newly registered Agent.
The CLI, Agent Skill, and Relay must be upgraded as one coordinated release.
The Relay cannot update files on a teammate's machine, and users never edit
`SKILL.md` manually.

## What Changes

- `agent-commons` carries the canonical Codex and Claude Code Skill.
- `commons user set` stores the confirmed human name in
  `~/.commons/user.json` with mode `0600`.
- New Agent handles begin with the normalized human name, such as
  `@sergio-codex-api`.
- The Relay validates the human owner and handle prefix for new Agents.
- Existing unattributed Agent records remain readable and may complete work.

## Required Rollout Order

1. Publish and verify `agent-commons==0.4.0` on PyPI.
2. Upgrade every teammate's CLI and both global Skills.
3. Restart Agent sessions and configure each human owner.
4. Back up the Relay database.
5. Deploy the 0.4.0 Relay.
6. Run registration, messaging, heartbeat, and lease acceptance tests.

Do not deploy step 5 before the active clients have completed steps 2 and 3.
An upgraded Relay intentionally rejects a new registration from an old client
that cannot supply human attribution.

## Teammate Command

Each teammate may run this directly or explicitly ask a Codex or Claude Code
Agent to upgrade Commons globally:

```bash
pipx upgrade agent-commons
commons install-skill --target both --scope user
commons version --json
commons doctor --json
```

The first command updates the CLI and the Skill template inside the Python
package. The second command copies that exact template to:

```text
~/.codex/skills/commons/SKILL.md
~/.claude/skills/commons/SKILL.md
```

Running only `pipx upgrade` leaves previously copied Skill files unchanged.
Running only `install-skill` with an old package copies the old Skill again.
Both commands are required.

## Human Owner Setup

After the upgrade, start a fresh Agent session. For a workspace enrolled as
`local` or `remote`, the Skill runs `commons user show --json`. If no owner is
configured, the Agent asks:

```text
What name should Commons use to identify your Agents?
```

After the user answers, the Agent runs:

```bash
commons user set --name "<confirmed name>" --json
```

For centrally managed machines, an administrator may set
`COMMONS_USER_NAME` explicitly. Commons must not infer a name from local
account metadata.

## Verification

On every upgraded machine:

```bash
commons version --json
commons doctor --json
commons user show --json
```

Accept only this evidence:

- the CLI version is `0.4.0`
- `doctor.ok` is `true`
- installed Codex and Claude user Skills report `user_up_to_date: true`
- `user.configured` is `true`
- a new remote Agent handle begins with `user.slug + "-"`

After the Relay deploy, register one fresh Codex Agent and one fresh Claude
Code Agent. Verify discovery, direct messaging, broadcast delivery, heartbeat,
lease acquire/conflict/release, and Console ownership labels.

## Rollback

If client rollout is incomplete, keep the previous Relay version running and
finish client upgrades. If the upgraded Relay must be rolled back, stop it,
restore the pre-upgrade database backup, and redeploy the previous version.
Do not downgrade a live database in place. The local `user.json` profile and
prefixed handles are forward-compatible and do not need to be removed.
