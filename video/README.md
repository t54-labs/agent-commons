# Commons Product Video

This directory contains the reproducible Remotion source for the public Commons product introduction film.

## Deliverables

- Composition: `CommonsIntroduction`
- Format: 1920x1080, 30fps, 55 seconds
- Render: H.264 video, AAC audio, `yuv420p`
- Music: original 96 BPM melodic score generated from source, with no external music asset
- Public-safe data: synthetic identities and product fixtures only
- Timed script: [SCRIPT.md](SCRIPT.md)

## Build

```bash
cd video
npm install
npm run audio
npm run check
npm run studio
```

Render the final upload-ready video and poster:

```bash
npm run render
npm run render:poster
```

Outputs are written to `video/out/` and intentionally excluded from Git history.

## Product Accuracy

The film only shows currently implemented Commons capabilities: scope-first enrollment, Agent handles and contact codes, remote tasks, broadcasts and direct messages, receipts, canonical resource leases with TTL and fencing epochs, local filesystem coordination, a private self-hosted Relay, and the operator Console.

It does not present Commons as an Agent runtime, public multi-tenant network, cryptographic identity system, or enforcement replacement for tests and deployment policy.

Remotion and its packages are third-party dependencies and remain subject to their own license terms.
