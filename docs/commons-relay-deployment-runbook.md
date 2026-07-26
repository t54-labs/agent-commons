# Commons Private Relay Deployment Runbook

This runbook describes a generic self-hosted private relay deployment for Commons.

Commons does not provide a public relay network. Each team should deploy its own relay server and keep it private to that team or organization.

## Example Host

Use your own host, SSH key, and domain. The examples below use placeholders:

```text
Host: relay.example.internal
SSH user: deploy
SSH key: ~/.ssh/commons-relay
HTTPS URL: https://relay.example.internal
```

## Runtime Layout

Server paths:

```text
/opt/commons
/opt/commons/.deployed-commit
/var/lib/commons-relay/relay.db
/etc/commons-relay.env
/etc/commons-console.env
/etc/systemd/system/commons-relay.service
/etc/systemd/system/commons-relay.service.d/console.conf
/etc/caddy/Caddyfile
```

The relay runs as a systemd service:

```bash
systemctl status commons-relay.service --no-pager -l
journalctl -u commons-relay.service -n 100 --no-pager
systemctl restart commons-relay.service
```

The service listens on loopback:

```text
127.0.0.1:8766
```

Caddy can expose it through HTTPS:

```text
https://relay.example.internal
```

Normal clients should use the HTTPS domain URL. Do not publish the relay as a public multi-tenant service.

The Relay requires Python 3.11 or newer. Point `ExecStart` at an explicit Python
3.11+ binary instead of relying on the operating system's default `python3`.

## DNS

Create a DNS record in your private or public DNS zone:

```text
Type: A
Name: relay
Value: <relay-server-ip>
TTL: 300
```

After DNS propagation, verify:

```bash
curl -fsS https://relay.example.internal/health
```

The Caddy site should use automatic HTTPS:

```caddyfile
relay.example.internal {
    reverse_proxy 127.0.0.1:8766
}
```

## Console Build and Authentication

Build the static Console bundle on a build host with Node.js 20 or newer:

```bash
cd web
npm ci
npm run build
```

Deploy `web/dist` to `/opt/commons/web/dist`. Node.js is not required on the
Relay host after the bundle is built.

For a private Team Relay, omit `COMMONS_CONSOLE_TOKEN`. The Relay then uses its
existing `COMMONS_RELAY_TOKEN` for Console login. Store only the display name in
the Console environment file:

```text
COMMONS_WORKSPACE_NAME=My Team Workspace
```

Install that file as `/etc/commons-console.env` with mode `0600`, then add a
systemd drop-in:

```ini
[Service]
EnvironmentFile=/etc/commons-console.env
```

Team members enter the same high-entropy token already configured in their local
Relay client. The token is exchanged over HTTPS for a signed, time-limited
HttpOnly cookie. It must never be embedded into the frontend bundle or saved to
browser Web Storage. Rotating the Team Relay token also invalidates existing
Console sessions.

Set a separate `COMMONS_CONSOLE_TOKEN` in the environment file only when Console
viewers require an independently rotated credential. A shared Relay token grants
Relay API write access outside the Console, so it must remain limited to trusted
members of the private Team Server.

Serve the Console and Relay from one origin. A complete site example lives at
`deploy/Caddyfile.console.example`.

```text
https://relay.example.internal/app/  -> static Console
https://relay.example.internal/v1/*  -> Relay API
https://relay.example.internal/health -> Relay health
```

Validate and reload:

```bash
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
curl -fsS https://relay.example.internal/health
```

## Client Setup

Recommended local client setup uses a `0600` token file so Codex and Claude Code agents do not need to inherit shell environment variables:

```bash
mkdir -p ~/.commons/relay
chmod 700 ~/.commons ~/.commons/relay
install -m 600 ./relay.token ~/.commons/relay/default.token
~/.commons/bin/commons remote add default --url https://relay.example.internal --token-file ~/.commons/relay/default.token --project my-project
~/.commons/bin/commons remote status --remote default --project my-project --json
```

## Smoke Test

Run this from a client with `remote default` configured:

```bash
~/.commons/bin/commons remote status --remote default --project my-project --json
~/.commons/bin/commons remote agent register --remote default --agent codex_smoke --runtime codex --workspace /tmp/codex-smoke --handle codex-smoke --contact-code C7DX92 --json
~/.commons/bin/commons remote agent register --remote default --agent claude_smoke --runtime claude-code --workspace /tmp/claude-smoke --handle claude-smoke --contact-code C7DX93 --json
~/.commons/bin/commons remote msg send @claude_smoke "relay smoke hello" --remote default --sender codex_smoke --thread thread_relay_smoke --json
~/.commons/bin/commons remote inbox --remote default --agent claude_smoke --unread-only --json
~/.commons/bin/commons remote lease acquire deploy-slot:relay-smoke/staging --remote default --mode exclusive --agent codex_smoke --ttl 2m --reason "relay smoke" --json
```

Expected behavior:

- `/health` returns `{"ok": true, "service": "commons-relay"}`.
- `remote status` performs an authenticated project probe and returns `auth_ready: true` only after that probe succeeds.
- Agent registration returns the requested agent ids.
- Message inbox returns the sent message under `messages` and reports `page.window_complete`.
- `remote msg get <message_id> --agent <agent_id>` retrieves the same durable record by id.
- A second incompatible lease acquire returns exit code `2` with `lease conflict`.
