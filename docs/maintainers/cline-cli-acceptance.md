# Cline CLI Acceptance Record

This record captures the first real Cline CLI coordination acceptance run for
the Commons 0.5 development line. It deliberately excludes Relay credentials,
private URLs, internal project names, message bodies, contact codes, and raw
transcripts.

## Environment

- Date: 2026-08-06
- Platform: macOS arm64
- Cline CLI: 3.0.51
- Commons client: 0.5.0 development source
- Coordination peer: a separately running Codex Agent
- Transport: a private self-hosted Commons Relay
- Isolation: temporary HOME and workspace for Commons installation and Cline
  execution

Cline authentication was configured through Cline's credential mechanism. No
provider credential was passed to Commons, written to the repository, included
in the Agent prompt, or sent through Relay messages.

## Human-Style Scenario

The operator gave Cline a natural-language task: use the globally installed
Commons Skill, join the already enrolled remote workspace, introduce itself to
the team, and coordinate with the Codex peer. The prompt did not provide
individual Commons commands, generated identifiers, or a message id.

Cline then performed the workflow itself:

1. Discovered the global Commons Skill from `~/.agents/skills/commons`.
2. Resolved the enrolled remote scope and used `cline` as its runtime.
3. Registered an attributed Agent with a user-prefixed handle and contact code.
4. Published a project broadcast and sent a direct message to the Codex peer.
5. Allowed the Codex peer to read, acknowledge, and reply to that message.
6. Resumed the interactive Cline session from a human follow-up that only said
   a teammate had replied.
7. Read the reply from its Commons inbox, acknowledged it, summarized the
   result to the operator, and sent an explicit offline heartbeat.

Relay-side audit state confirmed the Cline runtime label, both message
directions, the acknowledgement timestamp, and final offline presence.

## Automated Coverage

The committed suite complements this manual gate with deterministic checks for:

- Cline user and project Skill destinations;
- the packaged Cline bootstrap rule and stable CLI shim;
- Cline executable and version diagnostics;
- legacy duplicate-path reporting;
- runtime normalization that never persists `auto`;
- a Cline-labelled registration, plan, lease denial, direct message, release,
  and verification lifecycle;
- a real local Relay process with Codex, Claude Code, and Cline registrations.

## Known Runtime Limitation

Interactive Cline resume worked in the acceptance run. Cline 3.0.51 rejected a
headless JSON resume using an existing session id before accepting the follow-up
prompt. This is a Cline CLI resume-mode limitation, not a Commons messaging or
durability failure. Commons does not claim automatic wake-up of a terminated
agent process; that remains a separate runtime-adapter track.

## Release Interpretation

This gate supports the claim that Commons **works with Cline CLI** through its
Skill and CLI. It does not support claims of deterministic command interception,
background subscription, or passive wake-up. Those require the deferred Cline
plugin/runtime-adapter and recovery matrix.
