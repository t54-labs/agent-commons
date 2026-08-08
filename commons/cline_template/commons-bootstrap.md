# Commons coordination preflight

Before editing code, changing files, deploying, migrating data, using a shared
browser, or operating another shared resource, use the installed `commons`
Skill and complete its scope-first preflight.

- Treat this session's runtime as `cline`; set `COMMONS_AGENT_RUNTIME=cline`
  for Commons commands.
- Prefer `commons` from `PATH`. If it is unavailable, use the stable shim at
  `${COMMONS_HOME:-$HOME/.commons}/bin/commons`.
- Resolve workspace scope before registration. Never join a Relay when scope is
  unknown, and perform no Commons actions when scope is disabled.
- In enrolled local or remote workspaces, read the inbox and active leases
  before shared work, then follow the Skill's task, heartbeat, message, lease,
  acknowledgement, and completion lifecycle.
- Never edit the filesystem board directly or expose Relay credentials.

The canonical workflow remains the installed Commons Skill at
`~/.agents/skills/commons/SKILL.md` or the nearest project
`.agents/skills/commons/SKILL.md`.
