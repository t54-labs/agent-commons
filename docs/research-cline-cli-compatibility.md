# Commons Runtime Compatibility: Codex CLI, Claude Code CLI, and Cline CLI

**Research date:** 2026-08-04  
**Cline source snapshot:** [`6712d43`](https://github.com/cline/cline/tree/6712d43c69f4590204cdff10a93bb7abb83ad05c)  
**Scope:** Local terminal runtimes. This note evaluates the current Commons package and Skill against Codex CLI, Claude Code CLI, and Cline CLI. It proposes an implementation sequence but does not change product code.

## Executive conclusion

Commons can support all three CLIs without MCP. The standalone `commons` executable remains the protocol client; runtime-native Skills, rules, hooks, or plugins only decide when and how reliably that executable is called.

The current support level is uneven:

- **Claude Code CLI:** already has working baseline support. Commons installs the Skill to Claude Code's documented personal and project paths.
- **Codex CLI:** already works, but the user-level installer still writes to the legacy `~/.codex/skills` location. The current documented cross-agent location is `~/.agents/skills`; project installs already use the correct `.agents/skills` path.
- **Cline CLI:** the Commons CLI can already be called from Cline's shell tool, and project-local Commons Skills may be discovered through shared Agent Skills locations in some Cline builds. Commons does not yet install a canonical Cline user Skill, report Cline in `doctor`, or provide a Cline lifecycle adapter. It is therefore compatible in principle, not first-class supported today.

Cline has a standalone terminal agent, native `SKILL.md` discovery, always-on rules, shell execution, lifecycle hooks, plugins, and headless execution. A Commons installation can distribute its existing Python CLI through PyPI and let Cline invoke the `commons` executable through built-in shell execution or a small Cline adapter.

The important qualification is that a `SKILL.md` file alone is not a deterministic startup mechanism. Cline loads only skill metadata at startup and asks the model to invoke the full skill when relevant. Production integration should separate:

1. **Skill:** model-facing Commons workflow and commands.
2. **Rule:** always-visible instruction to perform Commons preflight.
3. **Plugin or lifecycle hooks:** deterministic registration, heartbeat, inbox checks, and pre-tool guards.
4. **External subscription process:** real-time Relay delivery and wake-up; a completed one-shot CLI process cannot receive later messages.

The strongest product direction is a Cline plugin that launches the existing Commons executable, with a file-hook adapter as a simpler fallback. MCP remains optional.

## Support matrix

| Capability | Codex CLI | Claude Code CLI | Cline CLI |
| --- | --- | --- | --- |
| Run the `commons` executable | Yes | Yes | Yes |
| Current Commons user Skill install | Legacy-compatible path | Canonical path | Not installed |
| Current Commons project Skill install | Canonical path | Canonical path | Incidental discovery only; no explicit target |
| Skill auto-selection | Model-selected, on demand | Model-selected, on demand | Model-selected, on demand |
| Always-on instructions | `AGENTS.md` | `CLAUDE.md` | Rules or `AGENTS.md` |
| Deterministic lifecycle surface | Native hooks | Native hooks | Plugin hooks; file hooks exist but have source/documentation drift |
| Can block risky tool use | `PreToolUse` | `PreToolUse` | Plugin/file pre-tool hook |
| True passive Relay wake-up | Requires runtime adapter | Requires runtime adapter | Plausible through plugin events and hub, but not yet proven |
| Commons status today | Supported with path debt | Supported baseline | Feasible, not first-class |

## Current Commons implementation audit

The current package is runtime-neutral at the Relay protocol layer: registration accepts arbitrary runtime strings, so `runtime: "cline"` needs no Relay schema change. The missing work is in installation, runtime identity, diagnostics, and lifecycle integration.

Confirmed gaps in the current source:

- `commons install-skill --target` accepts only `codex`, `claude`, or `both`.
- `commons doctor` checks only `codex` and `claude` executables and Skill locations.
- The user-level Codex target is `~/.codex/skills/commons`, while current Codex documentation names `~/.agents/skills/commons` as the canonical user path.
- The user-level Cline target `~/.cline/skills/commons` is absent.
- The shared Skill tells agents to register with `--runtime auto`, but the CLI currently sends the literal value `auto`; it does not resolve that value to `codex`, `claude-code`, or `cline`.
- The bundled Skill describes Codex and Claude Code installation explicitly and needs runtime-neutral wording before it is copied to Cline.

The `--runtime auto` issue is a correctness blocker for first-class Cline support. Runtime identity drives Console filtering and attribution, so the product must not silently register a Cline session as `auto` or guess from a source checkout. Prefer an explicit `COMMONS_AGENT_RUNTIME` supplied by each runtime adapter, with conservative process/environment detection only as a fallback.

## Codex CLI

Codex uses the same Agent Skills system in its CLI, IDE extension, and desktop surfaces. Skills are selected explicitly through `/skills` or `$skill-name`, or implicitly when a task matches the Skill description. Only Skill metadata is present initially; the full `SKILL.md` is loaded after selection ([Codex Skills documentation](https://developers.openai.com/codex/skills/)).

Current documented paths are repository `.agents/skills` directories from the working directory to the repository root, plus the user path `~/.agents/skills` ([Codex Skill locations](https://developers.openai.com/codex/skills/#where-codex-loads-local-skills)). Codex still recognizes `~/.codex/skills` as a legacy location in current builds, but OpenAI recommends moving to the shared `.agents` location ([OpenAI repository clarification](https://github.com/openai/codex/issues/14337#issuecomment-3736814900)). Commons should install the canonical path and offer an explicit compatibility mirror or migration check instead of creating duplicate active copies silently.

Codex now exposes native lifecycle hooks. `SessionStart` distinguishes `startup`, `resume`, `clear`, and `compact`; its output can add developer context. `PreToolUse` can intercept shell commands, `apply_patch`, MCP calls, and other local tools. Hooks can live in user or repository `.codex` configuration, but non-managed command hooks require an explicit trust review ([Codex Hooks documentation](https://developers.openai.com/codex/hooks/)). This is sufficient for deterministic Commons registration/reconciliation and pre-side-effect lease checks after the user trusts the adapter.

## Claude Code CLI

Claude Code's documented personal Skill path is `~/.claude/skills/<name>/SKILL.md`, and its project path is `.claude/skills/<name>/SKILL.md`; these exactly match the current Commons installer. Claude can select a Skill automatically from its description or the user can invoke it explicitly. Skill changes are detected live, except that a newly created top-level skills directory may require a restart ([Claude Code Skills documentation](https://code.claude.com/docs/en/slash-commands#where-skills-live)).

Claude Code also exposes the lifecycle controls Commons needs. `SessionStart` receives startup/resume context, `UserPromptSubmit` can inject new context, and `PreToolUse` receives structured tool input and can deny a call. A denial remains effective even under `--dangerously-skip-permissions`, which makes this a stronger enforcement boundary than prompt instructions alone ([Claude Code Hooks guide](https://code.claude.com/docs/en/hooks-guide)).

Local CLI support does not imply Claude cloud-session support. Remote Cowork and cloud sessions do not read a user's local `~/.claude/skills`; they require account-enabled Skills, committed project Skills, or a repository-declared plugin. Commons should describe local Claude Code CLI as supported and treat Claude-hosted sessions as a separate integration target.

## Cline CLI

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

## Recommended implementation plan

### Phase 1: first-class Skill and diagnostics support

Make the existing lightweight integration accurate across all three runtimes:

- add `cline` and `all` installer targets while preserving `both` as the Codex-plus-Claude compatibility alias;
- install Cline user Skills at `~/.cline/skills/commons` and project Skills at `.cline/skills/commons`;
- migrate Codex user installation toward `~/.agents/skills/commons`, detecting and reporting duplicate legacy copies rather than silently activating both;
- make the Skill wording runtime-neutral and keep the packaged template byte-identical across installed targets;
- resolve `--runtime auto` to a supported runtime, with runtime adapters setting `COMMONS_AGENT_RUNTIME` explicitly;
- extend `commons doctor --json` with Cline executable, Skill, rule, duplicate-path, and version checks;
- extend deterministic and real-runtime smoke manifests to accept `cline`.

For Cline specifically:

- installs the canonical Skill at `~/.cline/skills/commons/SKILL.md`;
- installs a uniquely named always-on rule at `~/.cline/rules/commons-bootstrap.md` that requires Commons preflight before shared side effects;
- resolves the PyPI-installed `commons` executable once and records a stable executable path for Cline-launched subprocesses;
- verifies discovery through an isolated Cline invocation and the runtime's configuration UI rather than assuming undocumented config subcommands;
- documents that existing Cline sessions must restart to guarantee fresh metadata and rules.

This provides feature parity with the current Codex/Claude Code prompt-driven workflow. It is lightweight, but model compliance remains probabilistic.

### Phase 2: deterministic runtime adapters

Expose one stable, idempotent Commons hook entry point, for example `commons runtime hook --runtime <runtime> --event <event>`, that reads host JSON from stdin and returns host-specific structured output. Keep Relay protocol behavior in Python and host configuration in thin adapters.

- **Codex:** install opt-in `SessionStart`, `UserPromptSubmit`, `PreToolUse`, and `SessionEnd` hooks without overwriting existing hook configuration. Respect Codex's hook trust workflow.
- **Claude Code:** install opt-in `SessionStart`, `UserPromptSubmit`, `PreToolUse`, and `SessionEnd` hooks through a managed plugin or merged settings fragment. Never overwrite unrelated user hooks.
- **Cline:** prefer a small global Cline plugin installed by the Commons CLI. Use file hooks only as a compatibility fallback.

The adapters should:

- register and heartbeat at run start/resume;
- reconcile inbox and active leases before the first risky tool;
- report selected tool activity and status transitions;
- release owned resources and mark the Agent offline at completion/cancel/shutdown.

If a plugin is not yet acceptable, use file hooks with an explicit multiplexer and never overwrite existing user hooks. Pair asynchronous `TaskStart` with a blocking, idempotent `PreToolUse` preflight.

### Phase 3: push delivery and wake-up

Run a supervised Commons subscriber outside the one-shot agent process. It should maintain a durable Relay cursor, reconnect after sleep/restart, and reconcile missed events. The subscriber can then use a validated Cline plugin external event, Cline hub operation, or a new `cline --id` invocation to deliver work. Keep periodic reconciliation as a correctness backstop even when push transport is available.

WebSocket transport alone does not wake a terminated model loop. The durable subscriber owns connectivity and queues messages; each runtime adapter determines whether to inject context at the next lifecycle boundary, resume an existing session, or create a new run. Product claims should distinguish transport delivery from agent attention.

## Acceptance and test boundaries

First-class support requires more than a successful file copy. The release gate should include:

1. **Installer tests:** clean and upgrade installs for every target and scope; no unrelated rules, hooks, or settings are overwritten.
2. **Discovery tests:** each runtime lists or invokes the Commons Skill from an isolated home directory.
3. **Identity tests:** registration records exactly `codex`, `claude-code`, or `cline`, never `auto`.
4. **Lifecycle tests:** startup, resume, compaction where applicable, first risky tool, normal completion, cancellation, and crash recovery.
5. **Coordination E2E:** Codex-to-Cline, Claude-to-Cline, and Cline-to-Cline direct messages, broadcasts, acknowledgements, task ownership, lease denial, renewal, release, and fencing behavior through a remote Relay.
6. **Recovery tests:** Relay disconnect, CLI restart, machine sleep/wake, stale cursor reconciliation, and expired session state.
7. **Security tests:** malicious message content, redaction, hook command injection, private workspace paths, token handling, and fail-open versus fail-closed behavior.
8. **Platform matrix:** macOS and Linux first. Claim Windows only after pipx installation, Skill paths, PowerShell/file hooks, and Cline's compiled binary are exercised together.

The Skill-only release can claim "works with" a runtime. The hook/plugin release can claim "automatic preflight and lifecycle coordination." Passive real-time delivery should remain experimental until the recovery matrix passes.

## Final recommendation

Add Cline as a first-class Commons runtime, not as a Claude Code alias. The immediate no-MCP integration is feasible through `~/.cline/skills`, `~/.cline/rules`, shell execution, and a stable Commons executable. Fix Codex's canonical user path and the unresolved `runtime auto` behavior in the same compatibility release so all three runtimes share one honest support contract.

For a reliable product experience, use native Codex and Claude hooks plus a Cline plugin as thin deterministic adapters, while Skills remain the human-readable workflow contract. Do not claim passive real-time delivery until an external-event/resume spike proves behavior across CLI exit, hub restart, Relay disconnect, and machine sleep/wake.
