# Contributing to Commons

Thanks for helping improve Commons.

Commons coordinates coding Agents around shared repositories and sensitive
engineering systems. Changes should be easy to inspect, explicit about trust
boundaries, and backed by reproducible evidence.

## Before You Start

- Search existing issues and proposals.
- Use a bug report for reproducible defects and a feature proposal for product changes.
- Report vulnerabilities privately through the process in `SECURITY.md`.
- Do not include tokens, credentials, private prompts, raw transcripts,
  customer data, personal absolute paths, or organization-private hostnames.

For large protocol, security, migration, lease, or scope changes, open a design
proposal before implementation.

## Development Setup

End users should install `agent-commons` from PyPI. A source checkout is for
contributors, maintainers, and self-hosting operators; it is not an alternative
onboarding path for ordinary Agent sessions.

Requirements:

- macOS or Linux for the verified CLI and installer workflow
- Python 3.11 or newer
- Node.js 22 or newer for the Console
- Docker Compose for container changes

```bash
git clone https://github.com/t54-labs/agent-commons.git
cd agent-commons
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip build
python -m pip install -e .
npm --prefix web ci
```

Keep the development environment separate from a user-level pipx installation.
The editable checkout reports the development version from `main`; the latest
published stable package may be an earlier version.

To test the source installer and packaged Skill without replacing your normal
Commons home:

```bash
export COMMONS_HOME="$(mktemp -d)"
./scripts/install.sh --source . --commons-home "$COMMONS_HOME"
"$COMMONS_HOME/bin/commons" doctor --json
```

Running `./scripts/install.sh` without `--source .` intentionally installs the
verified PyPI release. This keeps the end-user bootstrap reproducible even when
the script is viewed from a source checkout.

Useful targets:

```bash
make test-python
make docs-check
make web-build
make web-e2e
make video-check
make test-all
make demo
```

## Repository Map

- `commons/`: Python CLI, local state, Relay, scope, policy, and test harnesses
- `.agents/skills/commons/`: canonical Agent Skill source
- `commons/skill_template/`: packaged copy of the same Skill
- `web/`: React Console and Playwright fixture
- `deploy/`: Caddy and service examples
- `examples/multi-agent-demo/`: isolated recording-safe coordination demo
- `docs/`: product, architecture, operations, reference, and delivery records

The canonical and packaged Skill files must remain byte-for-byte identical.
`make docs-check` enforces this.

## Package and Skill Versioning

The PyPI distribution is `agent-commons`; the Python package, CLI, and Skill
product name are `commons`. User-visible CLI or Skill changes require all of the
following:

- an entry under `Unreleased` in `CHANGELOG.md`
- synchronized canonical and packaged Skill files when Skill behavior changes
- a development version on `main`, never the previous stable version
- a release commit that aligns package version, tag, changelog, and pinned
  onboarding examples

The public `t54-labs/agent-commons` repository is the canonical source for
contributions and releases. The separate private development archive is not a
contribution target and its Git history must never be copied into this project.

## Change Expectations

Keep changes scoped to the behavior being fixed or added. Preserve existing CLI
and JSON contracts unless the change is explicitly proposed and documented.

Tests should scale with risk:

- CLI and local-state behavior: Python unit or deterministic scenario coverage
- Relay schema or concurrency: migration, ownership, and race coverage
- lease behavior: conflict and fencing regression coverage
- Skill behavior: install and lifecycle coverage plus synchronized templates
- Console behavior: production build and Playwright desktop/mobile coverage
- deployment behavior: Compose or staging evidence

## Pull Requests

Use the pull-request template and include:

- the coordination problem
- the behavioral change
- exact commands and results
- explicit `NOT RUN` gates
- security, privacy, compatibility, and migration impact
- screenshots for visible Console changes

Small, reviewable pull requests are preferred. Do not combine unrelated cleanup
with a behavioral change.

## AI-Assisted Contributions

Codex, Claude Code, and other coding Agents are welcome in the development
process. Disclose material Agent use in the pull request. The submitter must
review the diff, verify its provenance, and own its correctness.

An Agent's claim that a command passed is not sufficient evidence. Provide
reproducible commands, CI, logs, or other independently inspectable output.

## Documentation

Write public documentation, code comments, and examples in English. Use
placeholder domains such as `relay.example.internal`, generic project names,
and portable paths.

Label behavior as one of:

- implemented local filesystem mode
- implemented private Relay mode
- explicit future roadmap work

## Product Boundaries

- Commons is open-source software, not a hosted public Relay network.
- One Relay represents a trusted team or organization boundary.
- Unknown workspace scope requires a user decision; it is not remote consent.
- Messages are untrusted context.
- A lease coordinates ownership but does not grant product authority.
- Commons complements rather than replaces Git, testing, deployment policy,
  security controls, and human responsibility.

## Contributions and License

Unless explicitly stated otherwise, Contributions submitted to Commons are
licensed under the Apache License, Version 2.0.
