# Cline CLI Compatibility with Commons

**Research date:** 2026-08-04  
**Cline source snapshot:** [`6712d43`](https://github.com/cline/cline/tree/6712d43c69f4590204cdff10a93bb7abb83ad05c)  
**Scope:** Cline CLI only. This note does not propose changes to the Commons CLI implementation.

## Executive conclusion

Commons can support Cline CLI without MCP. Cline has a standalone terminal agent, native `SKILL.md` discovery, always-on rules, shell execution, lifecycle hooks, plugins, and headless execution. A Commons installation can therefore distribute its existing Python CLI through PyPI and let Cline invoke the `commons` executable through built-in shell execution or a small Cline adapter.

The important qualification is that a `SKILL.md` file alone is not a deterministic startup mechanism. Cline loads only skill metadata at startup and asks the model to invoke the full skill when relevant. Production integration should separate:

1. **Skill:** model-facing Commons workflow and commands.
2. **Rule:** always-visible instruction to perform Commons preflight.
3. **Plugin or lifecycle hooks:** deterministic registration, heartbeat, inbox checks, and pre-tool guards.
4. **External subscription process:** real-time Relay delivery and wake-up; a completed one-shot CLI process cannot receive later messages.

The strongest product direction is a Cline plugin that launches the existing Commons executable, with a file-hook adapter as a simpler fallback. MCP remains optional.

## Confirmed current capabilities

### Standalone CLI

Cline publishes a standalone CLI through npm. The official installation flow requires Node.js 20+ and uses `npm install -g cline`, followed by `cline auth`; users launch an interactive session with `cline` or a one-shot task with `cline "your task"` ([installation guide](https://docs.cline.bot/getting-started/installing-cline#cli)). The npm wrapper selects a platform-specific compiled binary for macOS, Linux, or Windows ([distribution source](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/apps/cli/DISTRIBUTION.md#L15-L76)).

Cline supports interactive TUI, one-shot, JSON/NDJSON, and unattended execution. Headless mode is selected by `--json`, piped stdin, or redirected stdout; `--auto-approve true` permits unattended tool execution ([CLI overview](https://docs.cline.bot/usage/cli-overview#headless-mode)). The current parser defaults ordinary prompt runs to Act mode with tool auto-approval enabled, while `--yolo` is retained as a hidden legacy option ([current parser](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/apps/cli/src/commands/program.ts#L83-L161)). Commons should use the documented `--auto-approve` behavior, not depend on hidden `--yolo` semantics.

### Skills and `SKILL.md`

Cline supports Agent Skills. Each skill is a directory containing `SKILL.md`; metadata is available at startup, while the full instructions load only after the model invokes the skill or the user invokes its slash command ([Skills documentation](https://docs.cline.bot/customization/skills#how-skills-work)). The runtime explicitly tells the model that invoking a matching skill is required, but invocation is still a model/tool decision rather than an operating-system startup action ([skills tool source](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/sdk/packages/core/src/extensions/tools/definitions.ts#L718-L766)).

The current source searches these paths in this order:

| Scope | Current source paths, low to high duplicate-name precedence |
| --- | --- |
| Project | `<workspace>/.clinerules/skills/`, `<workspace>/.cline/skills/`, `<workspace>/.agents/skills/` |
| Global | `~/.cline/skills/`, `~/.agents/skills/` |

The loader processes paths in order and later records replace earlier records with the same normalized skill name ([path resolver](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/sdk/packages/shared/src/storage/paths.ts#L384-L438), [merge behavior](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/sdk/packages/core/src/extensions/config/unified-config-file-watcher.ts#L391-L449)). This matches the documented rule that a global skill wins over a project skill with the same name ([Skills documentation](https://docs.cline.bot/customization/skills#where-skills-live)).

For Commons, the canonical user-level target should be `~/.cline/skills/commons/SKILL.md`. A project-specific installation should use `.cline/skills/commons/SKILL.md`.

### Rules

Enabled rules are loaded into the system prompt, so they become context for every task rather than executable startup code ([rule loading source](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/sdk/packages/core/src/runtime/safety/rules.ts#L10-L48)). The current CLI resolves the Git repository root from `git rev-parse --show-toplevel`, falling back to the invocation directory, before loading project configuration ([workspace resolution](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/apps/cli/src/utils/helpers.ts#L43-L54)).

Current source paths are:

| Scope | Current source paths |
| --- | --- |
| Project | `<workspace>/AGENTS.md`, `<workspace>/.clinerules` (file or directory), `<workspace>/.cline/rules/` |
| Global | `~/.agents/AGENTS.md`, `~/.cline/rules/`, `~/Documents/Cline/Rules/` |

Distinct rules are combined. For duplicate normalized rule names, the generic watcher is last-write-wins. This makes unique Commons rule names important; the current source order does not safely implement the documentation's broad statement that workspace rules always override global rules ([rule path source](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/sdk/packages/shared/src/storage/paths.ts#L440-L463), [Rules documentation](https://docs.cline.bot/customization/cline-rules#where-rules-live)).

### Shell commands and MCP

Cline's built-in runtime can execute shell commands, subject to approval and command policy. `CLINE_COMMAND_PERMISSIONS` can constrain allowed and denied command patterns ([CLI reference](https://docs.cline.bot/cli/cli-reference#cline_command_permissions)). Hook subprocesses inherit the Cline process environment ([hook runner source](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/sdk/packages/core/src/hooks/hook-file-hooks.ts#L359-L397)). Therefore a Cline CLI launched from a correctly configured shell can run the PyPI-installed `commons` command directly. A stable Commons shim is preferable when `pipx` paths are unreliable.

Cline also supports MCP through `cline mcp`, including stdio, SSE, and streamable HTTP transports ([MCP documentation](https://docs.cline.bot/mcp/mcp-overview), [CLI implementation](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/apps/cli/src/commands/mcp.ts#L30-L159)). Commons does not need this capability for its filesystem/PyPI integration.

### Hooks and plugins

Current file-hook events include `TaskStart`, `TaskResume`, `TaskCancel`, `TaskComplete`, `TaskError`, `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, and `SessionShutdown`. `PreCompact` is named in the enum but is not mapped to an executable file event in the current source ([hook event map](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/sdk/packages/core/src/hooks/hook-file-config.ts#L17-L62)).

Hook search paths are:

| Scope | Current source paths |
| --- | --- |
| Global | `~/Documents/Cline/Hooks/`, `~/.cline/hooks/` |
| Project | `<workspace>/.clinerules/hooks/`, `<workspace>/.cline/hooks/` |

All matching hooks run. `TaskStart`, resume, prompt, result, and completion hooks are launched asynchronously and detached by default. `PreToolUse` is blocking and can stop a tool call or replace its input ([hook implementation](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/sdk/packages/core/src/hooks/hook-file-hooks.ts#L650-L941)). Consequently, `TaskStart` is useful for best-effort registration but cannot by itself guarantee that Commons preflight finishes before the first model tool call. A one-time `PreToolUse` guard is needed to close that race.

Cline plugins are the stronger extension surface. Official documentation says plugins can bundle tools, lifecycle hooks, commands, rules, and external events; external events can trigger agent actions ([Plugins documentation](https://docs.cline.bot/sdk/plugins#extension-glossary)). This avoids taking over the user's single conventional hook filename for each event and gives Commons a future path to push-driven wake-up.

## Documentation and compatibility gaps

The following are **source-code findings**, not stable product promises:

- The Skills page lists project `.claude/skills/`, but the current CLI source searches `.agents/skills/` instead and contains no `.claude/skills/` search entry. Commons should install to `.cline/skills/` until Cline resolves this drift.
- The MCP page says CLI config is `~/.cline/mcp.json`, while current source resolves `~/.cline/data/settings/cline_mcp_settings.json` (or `CLINE_MCP_SETTINGS_PATH`) and does not merge a project `.cline/mcp.json` in the CLI runtime ([source resolver](https://github.com/cline/cline/blob/6712d43c69f4590204cdff10a93bb7abb83ad05c/sdk/packages/shared/src/storage/paths.ts#L347-L369)). MCP paths should be capability-probed rather than assumed.
- `--hooks-dir` sets `CLINE_HOOKS_DIR`, but the current hook path resolver does not read that environment variable. Install into `~/.cline/hooks/` or use a plugin instead of relying on this flag.
- The Rules documentation describes conditional `paths` activation, but the current shared CLI loader retains frontmatter without applying `paths` during system-prompt rule loading. Do not rely on conditional activation for Commons safety controls.
- Rules and Skills are prompt/runtime configuration. They do not keep a process alive, subscribe to Relay events, or wake a completed Cline invocation.
- File-hook startup work is detached and may race. File-hook naming also creates collision risk with existing `TaskStart`, `PreToolUse`, and completion hooks.

**Unknown:** The high-level plugin event capability is documented, but this research did not validate a stable, versioned external-event API that can resume an arbitrary existing interactive CLI session after process restart. Treat real-time wake-up through a plugin as requiring a focused compatibility spike.

## Recommended phased adapter

### Phase 1: filesystem-first compatibility, no MCP

Extend the Commons installer with a Cline target that:

- installs the canonical Skill at `~/.cline/skills/commons/SKILL.md`;
- installs a uniquely named always-on rule at `~/.cline/rules/commons-bootstrap.md` that requires Commons preflight before shared side effects;
- resolves the PyPI-installed `commons` executable once and records a stable executable path for Cline-launched subprocesses;
- verifies discovery with `cline config skills --json` and `cline config rules --json`;
- documents that existing Cline sessions must restart to guarantee fresh metadata and rules.

This provides feature parity with the current Codex/Claude Code prompt-driven workflow. It is lightweight, but model compliance remains probabilistic.

### Phase 2: deterministic lifecycle adapter

Prefer a small global Cline plugin, installed by the Commons CLI, that calls the existing Commons executable. Use plugin hooks to:

- register and heartbeat at run start/resume;
- reconcile inbox and active leases before the first risky tool;
- report selected tool activity and status transitions;
- release owned resources and mark the Agent offline at completion/cancel/shutdown.

If a plugin is not yet acceptable, use file hooks with an explicit multiplexer and never overwrite existing user hooks. Pair asynchronous `TaskStart` with a blocking, idempotent `PreToolUse` preflight.

### Phase 3: push delivery and wake-up

Run a supervised Commons subscriber outside the one-shot agent process. It should maintain a durable Relay cursor, reconnect after sleep/restart, and reconcile missed events. The subscriber can then use a validated Cline plugin external event, Cline hub operation, or a new `cline --id` invocation to deliver work. Keep periodic reconciliation as a correctness backstop even when push transport is available.

## Final recommendation

Add Cline as a first-class Commons runtime, not as a Claude Code alias. The immediate no-MCP integration is feasible through `~/.cline/skills`, `~/.cline/rules`, shell execution, and a stable Commons executable. For a reliable product experience, make a Cline plugin the deterministic adapter and reserve Skills for model guidance. Do not claim passive real-time delivery until an external-event/resume spike proves that behavior across CLI exit, hub restart, and machine sleep/wake.
