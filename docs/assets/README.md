# Public Asset Provenance

This directory and the product source contain only public-safe fixture or
project-authored media. No production Relay, customer, credential, private
repository, or personal workspace data is represented.

## Console Evidence

`commons-console-overview.png` is a screenshot of the Commons Console using the
local synthetic fixture data exercised by the Playwright suite. The copy under
`video/public/` is the same public-safe screenshot used by the Remotion film.

## Social Preview

`commons-social-preview.html` is the editable source for the repository social
preview. `commons-social-preview.png` is rendered from that source with:

```bash
make marketing-assets
```

The rendering command is implemented in `scripts/render_social_preview.mjs`.

## Console Architecture Image

`web/public/commons-architecture.png` was generated specifically for Commons on
2026-07-26 with OpenAI's built-in image-generation tool. It used no reference
image or external visual asset. The prompt requested an original vertical
architectural photograph of connected white pedestrian bridges against a blue
sky, with no people, text, logos, watermark, or recognizable landmark.

## Product Video Audio

`video/public/commons-bed.m4a` is original procedural audio generated from the
deterministic source in `video/scripts/generate-audio.mjs`. It does not include
an external music sample.

When replacing an asset, record its origin and reproduction path here. Do not
add stock, scraped, customer, or production media without a documented license
and explicit publication review.
