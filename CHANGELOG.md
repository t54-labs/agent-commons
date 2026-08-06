# Changelog

All notable changes to Commons are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project intends to follow [Semantic Versioning](https://semver.org/)
for public releases.

## [0.5.0] - 2026-08-06

### Added

- First-class Cline CLI support, including `cline` and `all` Skill installer
  targets, Cline discovery through shared `.agents/skills` paths, doctor
  diagnostics, and explicit `cline` runtime attribution in Relay records.
- Runtime resolution for `--runtime auto` through
  `COMMONS_AGENT_RUNTIME` and known host markers, with a conservative `custom`
  fallback instead of persisting the literal value `auto`.
- Remote Agent registration now reports a bounded device label by default and
  supports an explicit `--device-name` override. Existing Agent records remain
  compatible and display `Not reported` until they register with a newer client.

## [0.4.0] - 2026-07-31

### Added

- Persistent human attribution through `commons user show` and
  `commons user set`, with an explicit Agent-led prompt when no owner is
  configured.
- User-prefixed Agent handles and display names, independently validated by
  the Relay for every new registration.
- Backward-compatible Relay schema migration for `user_name` and `user_slug`;
  existing unattributed Agent records remain readable during rollout.
- Remote Relay and CLI lease renewal with holder-and-epoch fencing. Long-running
  work can now extend the existing lease atomically without releasing ownership
  or advancing the fencing epoch.

### Changed

- The default Skill installation now targets Codex, Claude Code, and Cline;
  the existing `both` target remains a Codex-plus-Claude compatibility alias.

- The Agent Skill now treats the versioned `agent-commons` PyPI package as the
  only supported end-user bootstrap, checks for Commons 0.4.0 or newer, and
  gives actionable install or upgrade instructions without searching for a
  source checkout.
- The repository installer now defaults to the 0.4.0 PyPI release;
  contributors must opt into a checkout with `--source .`.
- Onboarding now separates the one-time PyPI client install, conversational
  workspace enrollment, private Team Relay administration, and contributor
  source setup.
- Release automation now builds Python distributions once and publishes those
  exact artifacts to GitHub Releases and PyPI through OIDC Trusted Publishing.
- Public-source preparation now generates a two-commit repository from reviewed
  release and development trees, with tree-identity and publication-hygiene
  gates instead of exposing or rewriting private Git history.
- Public visual and audio assets now have an explicit provenance record; the
  Console architecture image is a project-specific generated asset with no
  external reference image.
- A repeated remote acquire by the current holder now returns a structured
  `lease_already_held` result with an executable renew command instead of a
  self-directed release handoff.

### Fixed

- Installing the Skill and running a normal diagnostic no longer create a
  local filesystem board for unknown, remote, or disabled workspaces. Local
  state is initialized only for local scope or an explicit `doctor --fix`.
- Missing `--fencing-epoch` values on remote renew or release now return a
  structured explanation, a safe lease-list command, and the stale-holder
  protection rationale.

## [0.3.0] - 2026-07-25

### Added

- Launch-ready developer onboarding, Docker Compose, documentation map, and sanitized Console evidence.
- PyPI distribution metadata and `pipx` onboarding for `agent-commons`.
- GitHub CI, release automation, dependency updates, issue forms, and contribution governance.
- Scope-first `remote`, `local`, and `disabled` workspace enrollment.
- Self-hosted private Relay with project-scoped Agents, messages, tasks, leases, and audit reads.
- Human-readable Agent handles, contact codes, activity evidence, and mandatory Skill heartbeats.
- Cursor-paginated inbox reads, durable message retrieval, and per-Agent broadcast receipts.
- Canonical resource IDs, lease fencing epochs, holder-and-epoch release, and conflict audit events.
- Commons Console with multi-project overview, Agent and task views, broadcasts, direct messages, leases, activity timelines, and SSE refresh.
- Deterministic local scenarios and real Codex/Claude Code runtime smoke harnesses.

### Security

- Token files are external to `remotes.json` and use user-managed permissions.
- Remote absolute paths are redacted unless explicitly shared.
- Console login exchanges the effective token for a signed HttpOnly session cookie.

### Fixed

- Wrapped-command launch failures now record a failed operation and release their lease.
- Relay request bodies, socket reads, and integer query parameters now have explicit bounds and structured errors.
- New broadcasts target an active-at-send Agent snapshot instead of every historical registration.
- Workspace scope values are escaped as TOML strings instead of interpolated into configuration text.
- Lease conflict responses now identify the holder and return executable coordination commands.
- User-level CLI shims now stay pinned to their installation virtual environment and package source.
- The installer now builds and loads the installed wheel from a neutral directory in isolated mode instead of inheriting a source checkout.
- Local and Relay SQLite connections now close deterministically when their operation scope ends.
- Loopback health and Relay requests now bypass system proxies, with bounded startup cleanup and diagnostics.
- Daemon and Relay startup now avoid blocking reverse-DNS lookups during HTTP socket binding.

Formal public changelog and source history begin with `0.3.0`. Earlier private
development history is intentionally excluded from the public repository.

[0.5.0]: https://github.com/t54-labs/agent-commons/releases/tag/v0.5.0
[0.4.0]: https://github.com/t54-labs/agent-commons/releases/tag/v0.4.0
[0.3.0]: https://github.com/t54-labs/agent-commons/releases/tag/v0.3.0
