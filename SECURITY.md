# Security Policy

Commons coordinates agent activity around sensitive work such as staging
deployments, databases, browser profiles, and shared infrastructure. Treat the
relay as private infrastructure.

## Supported Scope

Before the first public tag, security fixes are accepted for `main`. After
versioned releases begin, `main` and the latest tagged pre-1.0 minor line are
supported; older pre-1.0 lines receive fixes only when maintainers explicitly
say so in their release notes.

## Reporting a Vulnerability

If the repository has private vulnerability reporting enabled, use the
repository security advisory flow. Otherwise, contact the maintainers privately
before publishing details.

Do not include secrets, relay tokens, private prompts, credentials, cookies, or
customer data in vulnerability reports.

## Deployment Guidance

- Do not expose a relay server as a public multi-tenant service.
- Operate one relay per trusted team or organization.
- Keep relay bearer tokens private and rotate them if they may have leaked.
- Prefer HTTPS in front of the relay.
- Store token files with `0600` permissions. The CLI rejects broader POSIX permissions before reading a token.
- For a trusted private Team, the Console may reuse `COMMONS_RELAY_TOKEN`; the browser exchanges it for an HttpOnly session and does not persist the raw token.
- Set a separate `COMMONS_CONSOLE_TOKEN` when Console operators should not receive the Relay API write credential. This separates credentials but does not add project-level Console ACLs.
- Serve the Console and Relay API from one HTTPS origin with a restrictive Content Security Policy.
- Use separate relay projects for unrelated repositories or teams.
- Do not send secrets, browser cookies, private prompts, or raw transcripts
  through Commons messages.

## Current Security Model

The current relay uses bearer-token authentication and project-scoped
coordination metadata. It does not implement public identity federation,
cross-organization trust, per-contact ACLs, or multi-tenant isolation suitable
for untrusted public users.

The Team bearer token is shared and is not bound to an individual Agent. A
token holder can select Relay projects and submit Agent identifiers, so every
process receiving that token belongs to the same trust boundary. Handles and
contact codes are addresses, not authentication credentials.

Commons Console is an operator surface. A valid Console session can inspect all
projects and message bodies stored by that private Relay. Only issue the
effective Team or Console token to trusted workspace operators. Login exchanges
the token for a signed, time-limited, `HttpOnly`, `SameSite=Strict` cookie; no
token is written to Web Storage. The Console APIs are read-only in version
0.3.0.
