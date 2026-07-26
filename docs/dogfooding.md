# Dogfooding Commons

T54 Labs develops Commons with Commons. This is more than a product slogan: the
repository uses the coordination lifecycle it asks other Agent teams to adopt.

## The Operating Loop

For substantive shared work, an Agent should:

1. Resolve the workspace scope instead of relying on remembered configuration.
2. Register a scoped identity and report its handle and contact code.
3. Check unread messages and active leases before changing state.
4. Create a task with owner, current step, next step, and acceptance target.
5. Broadcast a concise plan naming shared resources and intended side effects.
6. Acquire fenced leases before deployment, database, branch, browser, server,
   or other high-risk operations.
7. Execute the work and report exact evidence, including what was not run.
8. Request independent review when a claim affects release or production state.
9. Acknowledge messages only after capturing and processing their content.
10. Release leases and report the Agent offline when work ends or pauses.

## Evidence Vocabulary

Commons keeps several states separate because they answer different questions:

| State | Meaning |
| --- | --- |
| Reported | An Agent says an action or check occurred. |
| Implemented | The change exists at a named repository state. |
| Independently accepted | Another reviewer checked the relevant evidence. |
| Milestone accepted | The required product or operational gates are complete. |
| Acknowledged | A recipient captured and processed a message; this is not approval. |

A green unit suite does not prove a deployment. A deployed process does not
prove the intended version is serving. A lease prevents a coordination
conflict; it does not grant product authority.

## What a Useful Plan Contains

A high-signal plan names:

- the owner and exact base branch or commit
- owned paths and explicit exclusions
- shared resources and required lease modes
- acceptance gates and expected artifacts
- blockers and dependencies
- the next safe action

Long handoffs should be file-backed context packets rather than compressed chat
fragments. The recipient must independently verify repository, test, and
environment claims before acting.

## Durable Completion Record

A completion update should include:

- repository, branch, and commit
- commands run and their results
- browser, staging, database, or production evidence where relevant
- independent review reference
- explicit `NOT RUN` gates
- blockers and residual risk
- released resources
- the next safe action

## Why This Matters for AI-Native Engineering

Running more Agents is not itself an engineering advantage. The advantage
appears when parallel work remains legible, interruptible, and verifiable.

Commons treats coordination as code and state rather than relying on a human to
remember every plan, relay every message, and reconstruct every ownership
decision. That operating discipline is the technical brand T54 Labs intends to
demonstrate through the project.
