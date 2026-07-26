# Commons Open-Source Launch Campaign

## Campaign Decision

Launch Commons as the **private coordination control plane for coding Agents**,
not as another Agent runtime, orchestration framework, or chat application.

The campaign idea is:

> **See how your agents work together.**

The hook is:

> **Parallel agents are easy. Coordinated engineering is not.**

The product line is:

> **Commons is the shared control plane for Codex, Claude Code, and other coding Agents across sessions, repositories, machines, and shared infrastructure.**

This framing is both differentiated and defensible. Codex and Claude Code
already communicate strong native multi-Agent stories. Commons should not claim
to replace those products. It should make visible the operational layer they do
not share with each other.

## Market Context

Last reviewed: 2026-07-24.

- The [Codex app](https://openai.com/index/introducing-the-codex-app/) positions itself as a command center for running multiple Codex Agents in parallel with worktree isolation.
- [Claude Code Agent teams](https://code.claude.com/docs/en/agent-teams) provide shared tasks and direct messaging inside Claude Code, and are documented as experimental.
- The [A2A protocol](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) standardizes communication between independent Agent systems.
- [MCP Agent Mail](https://github.com/Dicklesworthstone/mcp_agent_mail) provides mail-style identities, messages, history, and advisory file leases through an MCP server.

Commons occupies a more operational coding boundary:

- independently started sessions rather than one required lead
- mixed runtimes rather than one vendor ecosystem
- shared side effects rather than only file isolation
- scope-first privacy rather than implicit global enrollment
- canonical resources, TTLs, and fencing epochs rather than intent prose alone
- claims, evidence, acknowledgement, and acceptance kept distinct

Do not publish comparative claims such as "first," "only," "safer than," or
"production-ready" without independently verifiable evidence.

## Campaign Objectives

1. Make the problem recognizable within ten seconds.
2. Let a developer understand the product boundary within thirty seconds.
3. Let a technical user run a deterministic proof within five minutes.
4. Earn trust through inspectable engineering evidence rather than AI hype.
5. Establish T54 Labs as a team operating genuinely AI-native engineering systems.
6. Recruit design partners, Contributors, and maintainers before optimizing for raw stars.

## Priority Audiences

### 1. Multi-Agent Power Users

Developers who keep several Codex, Claude Code, or terminal Agent sessions open.
Their pain is human message relaying, hidden intent, and surprise conflicts.

Call to action: run the six deterministic scenarios, then install the Skill.

### 2. AI-Native Engineering Teams

Teams moving from individual experiments to shared staging, databases,
deployments, and release processes.

Call to action: deploy one private Relay for a pilot repository and define five
canonical high-risk resources.

### 3. Platform and Developer-Experience Engineers

People responsible for policy, deployment safety, audit, and reproducibility.

Call to action: inspect lease fencing, scope resolution, JSON contracts, and
self-hosting boundaries.

### 4. Agent Tool Builders

Maintainers of runtimes, Agent frameworks, worktree tools, MCP systems, or A2A
implementations.

Call to action: discuss adapters and interoperability without changing the core
CLI-first boundary.

## Message Pillars

### Cross-Runtime Coordination

Commons lets separately started Codex and Claude Code sessions discover and
message one another without requiring one runtime to own the other.

Proof:

- one portable Skill
- user-scoped installation for both runtimes
- readable handles and contact codes
- private Relay across machines

### Shared-Side-Effect Safety

Worktrees isolate code checkouts. Commons coordinates resources outside the
checkout: deployments, databases, branches, browser profiles, ports, and
servers.

Proof:

- canonical resource IDs
- compatibility modes
- TTL and holder ownership
- monotonically increasing fencing epochs
- denial audit events

### Privacy by Enrollment

A globally installed Skill does not silently join personal or client
repositories to a work network.

Proof:

- explicit `remote`, `local`, and `disabled` modes
- unknown scope asks the user
- project-scoped messages, leases, and discovery
- self-hosted Team Relay rather than public default infrastructure

### Evidence over Claims

Commons carries Agent status but does not treat prose as proof.

Proof:

- structured tasks and exact steps
- durable IDs and audit history
- explicit acknowledgement semantics
- dogfooding discipline and reproducible test gates

## T54 Labs Brand Narrative

T54 Labs should present Commons as infrastructure extracted from real operating
experience:

> We did not start by designing a social network for Agents. We started with a
> practical problem: several Codex and Claude Code sessions were touching the
> same repositories, staging environments, databases, and servers, while a
> human relayed every plan and handoff. Commons is the control plane we built to
> make that work explicit.

The brand attributes are:

- technically serious without sounding enterprise-generic
- AI-native without anthropomorphic spectacle
- opinionated about trust boundaries and evidence
- lightweight enough to understand and self-host
- honest about advisory versus enforced behavior

Avoid:

- "autonomous software company" language
- imaginary productivity multipliers
- claims that Agents no longer need human authority
- calling a bearer-token private Relay multi-tenant or zero-trust
- presenting the private T54 Labs Relay as a public service

## Launch Asset Stack

Every public claim should point to one of these proof assets:

| Asset | Purpose | Repository source |
| --- | --- | --- |
| GitHub README | Ten-second category and five-minute activation | `README.md` |
| Console product screenshot | Proves this is a working operator surface | `docs/assets/commons-console-overview.png` |
| Social preview | Makes links recognizable and branded | `docs/assets/commons-social-preview.png` |
| 30-second clip | Shows conflict prevention before explanation | `docs/maintainers/demo-script.md` |
| 90-second product demo | Shows plan, denial, direct coordination, and handoff | `docs/maintainers/demo-script.md` |
| Technical walkthrough | Explains scope, Relay, leases, fencing, and audit | `docs/architecture.md` |
| Deterministic suite | Reproducible proof without external infrastructure | `make demo` |
| Docker stack | One-command private Relay and Console | `compose.yaml` |
| Dogfooding note | Connects product mechanics to T54 Labs practice | `docs/dogfooding.md` |

## Hero Demo Story

Do not begin with installation. Begin with a collision.

1. A Codex Agent acquires `deploy-slot:commons-demo/staging` and starts a 45-second deploy.
2. A Claude Code Agent tries to run staging smoke and is denied before the script begins.
3. Claude discovers the holder and sends a direct message requesting handoff.
4. The Console shows both plans, the lease, the blocked operation, and the message.
5. Codex publishes evidence and releases the lease.
6. Claude acquires the next fenced epoch and completes smoke.

End with:

> Two Agent products. One shared engineering world. No human copy-pasting status between them.

## Channel Plan

### GitHub

- Recreate the verified `v0.3.0` source tag and Release assets in the public
  `t54-labs/agent-commons` repository after every source-publication gate passes.
- Set the repository description and topics before the first source push and
  public announcement.
- Upload the social preview image in repository settings.
- Enable Discussions with `Ideas`, `Show and tell`, and `Q&A` categories only
  after moderation ownership is assigned.
- When Discussions are enabled, pin one "Start here" post linking the
  five-minute path and design-partner contact.

### T54 Labs Website

Publish a technical launch essay rather than a product landing page first.

Suggested title:

> Parallel Agents Are Easy. Coordinated Engineering Is Not.

Essay structure:

1. the human-relay failure
2. why worktrees and runtime-native teams are necessary but incomplete
3. the shared-side-effect problem
4. scope-first privacy
5. fenced leases and evidence
6. a real demo
7. why T54 Labs is open-sourcing the control plane

### Hacker News

Suggested title:

> Show HN: Commons – a self-hosted control plane for Codex and Claude Code

Opening comment:

> We built Commons after running multiple coding Agent sessions against shared
> staging, databases, branches, and servers. Native multi-Agent tools help run
> workers; Commons coordinates independently started sessions across runtimes
> and machines. It is CLI/Skill-first, self-hosted, and does not require MCP.
> The unusual part is resource leases with fencing epochs plus explicit
> remote/local/disabled workspace scope. The deterministic demo runs without
> external infrastructure. We would especially value criticism of the trust
> and enforcement boundaries.

### X Thread

Post 1:

> Parallel coding Agents are easy to start. The hard part is when Codex and
> Claude Code touch the same staging environment, database, branch, browser, or
> server without knowing each other's plan. We built Commons to coordinate
> those independently started sessions.

Post 2:

> Commons is not another Agent runtime. It is a private, self-hosted control
> plane: scoped identities, plans, tasks, direct messages, broadcasts, resource
> leases, fencing epochs, and an operator Console.

Post 3:

> The demo: Codex starts a deploy. Claude tries to smoke staging. Commons blocks
> the overlap before the command runs, identifies the holder, carries the
> handoff, then grants the next fenced lease.

Post 4:

> Privacy is scope-first. Installing the Skill globally does not enroll every
> repo. Each workspace is remote, local-only, or disabled. Unknown means ask the
> user, not join the work network.

Post 5:

> No MCP required. The default path is a portable Skill plus a scriptable CLI.
> Cross-machine teams can run their own lightweight Relay and Console with
> Docker Compose.

Post 6:

> Commons is Apache-2.0 and built by T54 Labs using Commons itself. We want
> design partners who are already operating mixed Agent sessions on real shared
> infrastructure.

### LinkedIn

> AI-native engineering is moving from one assistant per developer to several
> independent Agents working across repositories and machines. That creates a
> new control-plane problem: intent, ownership, shared resources, evidence, and
> handoff. T54 Labs is open-sourcing Commons, a private coordination
> layer for Codex, Claude Code, and other CLI Agents. It is deliberately not an
> Agent launcher or public network. It is the operational layer between Agents
> and the engineering systems they share.

### Developer Communities

Do not cross-post identical launch copy. Share the artifact that matches each
community:

- CLI and Agent communities: the short collision demo
- distributed-systems communities: fencing and stale-holder behavior
- security communities: scope, bearer-token limits, and untrusted messages
- DevOps communities: deployment, database, and browser ownership
- open-source communities: installer, Compose, governance, and contribution path

## Campaign Cadence

### T-7 to T-4: Private Proof

- Recruit five design partners already using at least two concurrent sessions.
- Have each run the installer and deterministic demo without live assistance.
- Record time to first successful `doctor`, first demo, and first private Relay.
- Fix every P0/P1 activation failure before public announcement.

### T-3: Technical Teaser

- Publish a silent 15-second clip of the lease denial and handoff.
- Use only the line "Parallel agents are easy. Coordinated engineering is not."
- Invite a small number of technical reviewers, not broad signups.

### T-1: Maintainer Readiness

- Freeze the release candidate commit.
- Complete security, licensing, secrets, and private-path scans.
- Capture all final images and videos from the frozen commit.
- Prepare channel-specific posts and assign a responder for launch day.

### T0: Public Launch

- Push the audited clean history to the already-public repository.
- Verify anonymous clone, README images, release assets, and issue forms.
- Recreate the verified GitHub release, confirm `main` CI, and publish the T54
  Labs essay.
- Post Hacker News first, then the X thread and LinkedIn post.
- Respond to technical criticism with code or docs links rather than slogans.

### T+1 to T+3: Proof Follow-Up

- Publish the five-minute technical walkthrough.
- Turn repeated objections into a visible FAQ or issue.
- Label first-contributor issues that are independently scoped and tested.
- Thank external reviewers and link fixes to their reports.

### T+7: Engineering Deep Dive

- Publish "Why Commons Uses Fencing Epochs" with a stale-holder sequence.
- Share activation and failure data without collecting private Relay telemetry.
- Announce the first accepted external contribution or design partner result.

### T+14: Campaign Review

- Compare traffic, activation, contribution, and support load with targets.
- Decide whether to invest next in distribution, adapters, auth, or core reliability.
- Publish a short transparent retrospective and updated roadmap.

## Measurement

Commons should remain telemetry-free by default. Use aggregate public and
voluntary signals:

### Awareness

- GitHub unique visitors and referring sites
- social preview impressions and demo completion
- star conversion from unique repository visitors

### Activation

- release downloads
- voluntary reports of successful `doctor`, `make demo`, and Compose startup
- median time to first successful local demo in design-partner sessions
- number and category of install failures

### Engagement

- substantive issues and Discussions rather than raw count
- external pull requests reaching review
- repeat Contributors
- requests for real integrations or deployment guidance

### Trust

- security reports handled within the published response window
- percentage of defects with reproducible evidence
- number of documentation corrections accepted
- unresolved P0/P1 issues at each campaign checkpoint

Initial two-week targets should be set after the five-person private proof. Do
not invent public growth numbers before measuring the baseline.

## Objection Handling

### "Codex and Claude Code already have multi-Agent features."

Correct. Commons does not replace them. It coordinates independently started
sessions across products, machines, and shared non-file resources.

### "Why not use Git or worktrees?"

Use them. They are authoritative for code and excellent for checkout isolation.
They do not express a planned database migration, current deployment owner, or
browser-profile handoff.

### "Why not MCP or A2A?"

MCP and A2A solve broader tool and Agent interoperability problems. Commons is
an operational product with coding-specific scope, tasks, leases, fencing, and
audit. Future adapters can coexist with the CLI-first core.

### "Is a lease actually enforced?"

Inside Commons wrappers or an integration that validates lease and fencing
state, yes. A separate process can bypass advisory coordination. The docs must
state that boundary clearly.

### "Can I use the T54 Labs Relay?"

No public Relay is promised. Deploy your own private Relay for your trusted
team. The source code and deployment material are the open product.

### "Does Commons store prompts or chain-of-thought?"

No such data is required. Commons stores coordination metadata and the message
content users or Agents explicitly send. Secrets, raw transcripts, and private
prompt content should not be sent.

## Campaign Exit Criteria

The launch campaign is ready only when:

- an anonymous developer can clone and pass the five-minute path
- CI is green on the release candidate
- the release tag matches package metadata
- GitHub identifies Apache-2.0 correctly
- the Console screenshot and social preview contain only fixture data
- no private path, hostname, token, prompt, or customer data is present
- self-hosting and security limitations are visible before deployment
- a rollback plan exists for the public release announcement and package assets
- at least two external reviewers can explain what Commons is not
