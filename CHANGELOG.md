# Changelog

All notable changes to Commons are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project intends to follow [Semantic Versioning](https://semver.org/)
for public releases.

## [Unreleased]

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

Formal changelog tracking begins with `0.3.0`; earlier development history is
available in Git.

[Unreleased]: https://github.com/t54-labs/commons/commits/main
[0.3.0]: https://github.com/t54-labs/commons/releases/tag/v0.3.0
