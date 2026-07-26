# Commons Documentation

This directory separates the shortest path to a working Commons deployment
from the deeper product and implementation records used by maintainers.

## Start Here

| Document | Use it when |
| --- | --- |
| [Getting Started](getting-started.md) | You want to install Commons, choose a workspace scope, or connect to a Team Relay. |
| [Why Commons](why-commons.md) | You want to understand the problem boundary and how Commons fits with adjacent agent tooling. |
| [Architecture](architecture.md) | You need the components, trust boundaries, consistency model, and failure behavior. |
| [Dogfooding Commons](dogfooding.md) | You want the operating discipline used by T54 Labs and this repository. |

## Operate Commons

| Document | Use it when |
| --- | --- |
| [Open-Source and Self-Hosting Model](open-source-self-hosting.md) | You are deciding Relay and project boundaries for a team. |
| [Relay Deployment Runbook](commons-relay-deployment-runbook.md) | You are deploying the Relay and Console behind HTTPS. |
| [Security Policy](../SECURITY.md) | You need the current security model or vulnerability-reporting process. |
| [End-to-End Test Plan](commons-e2e-test-plan.md) | You are validating local, Relay, runtime, or browser behavior. |

## Integrate and Extend

| Document | Use it when |
| --- | --- |
| [CLI and Skill Specification](commons-cli-and-skill-spec.md) | You need command contracts, JSON shapes, or Skill lifecycle rules. |
| [Commons Skill](../.agents/skills/commons/SKILL.md) | You are reviewing the instructions installed into Codex and Claude Code. |
| [Multi-Agent Demo](../examples/multi-agent-demo/README.md) | You want a recording-safe contention and handoff scenario. |

## Product and Delivery Records

These documents are intentionally detailed. They are design and delivery
records, not the recommended first read for a new user.

| Document | Purpose |
| --- | --- |
| [Product Design](commons-product-design.md) | Product model, interaction design, and operational primitives. |
| [Requirements and Delivery Plan](commons-requirements-delivery-plan.md) | Requirements, test boundaries, milestones, and task decomposition. |
| [Relay Server Plan](commons-relay-server-plan.md) | Remote coordination design and rollout decisions. |
| [Feedback Hardening Plan](commons-feedback-hardening-plan.md) | Reliability and trust improvements derived from real use. |
| [Implementation Status](commons-implementation-status.md) | Implemented, deferred, and verified product surface. |
| [Roadmap](commons-roadmap.md) | Planned milestones and release gates. |

## Governance and Release

| Document | Purpose |
| --- | --- |
| [Contributing](../CONTRIBUTING.md) | Development setup, evidence, and pull-request expectations. |
| [Governance](../GOVERNANCE.md) | Maintainer roles, decisions, releases, and AI-assisted contribution policy. |
| [Changelog](../CHANGELOG.md) | Released and unreleased user-visible changes. |
| [Code of Conduct](../CODE_OF_CONDUCT.md) | Community standards and enforcement. |

## Maintainer Material

| Document | Purpose |
| --- | --- |
| [Launch Campaign](maintainers/launch-campaign.md) | Positioning, channels, campaign cadence, copy, and success metrics. |
| [Demo and Recording Script](maintainers/demo-script.md) | Reproducible short and long product demos. |
| [Release Checklist](maintainers/release-checklist.md) | Technical and communication gates for a public release. |

## Documentation Rules

- Use English in public documentation and examples.
- Use placeholder organizations, domains, paths, and project identifiers.
- Label future work explicitly; do not describe roadmap items as implemented.
- Keep secrets, private prompts, raw transcripts, tokens, and customer data out of examples.
- Treat the CLI `--help` output and tests as the executable contract when prose drifts.
