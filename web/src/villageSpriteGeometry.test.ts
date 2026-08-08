import { describe, expect, it } from "vitest";

import {
  SHADOW_CENTER_Y,
  SHADOW_HEIGHT,
  visibleFootY,
  groundedSpriteY,
} from "./villageSpriteGeometry";


describe("village sprite grounding", () => {
  it("keeps every walk frame on the shared ground line at every rendered scale", () => {
    for (const frame of Array.from({ length: 16 }, (_, index) => index)) {
      for (const scale of [0.55, 0.8, 1, 1.35]) {
        const spriteY = groundedSpriteY(frame, scale);
        expect(visibleFootY(frame, scale, spriteY)).toBeCloseTo(0, 6);
      }
    }
  });

  it("keeps the visible foot inside the shadow instead of above it", () => {
    const shadowTop = SHADOW_CENTER_Y - SHADOW_HEIGHT / 2;
    const shadowBottom = SHADOW_CENTER_Y + SHADOW_HEIGHT / 2;

    expect(shadowTop).toBeLessThanOrEqual(-4);
    expect(shadowBottom).toBeGreaterThanOrEqual(4);
    expect(0).toBeGreaterThan(shadowTop);
    expect(0).toBeLessThan(shadowBottom);
  });
});
