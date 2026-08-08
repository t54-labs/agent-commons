const WALK_FRAMES_PER_DIRECTION = 4;

// The generated walk cycle deliberately moves the legs by one pixel between
// frames. Anchor the lowest visible pixel back to the shared ground line so the
// character cannot drift away from its Phaser shadow.
const FRAME_BOTTOM_PADDING = [2, 1, 3, 1] as const;

export const SHADOW_CENTER_Y = 0;
export const SHADOW_WIDTH = 32;
export const SHADOW_HEIGHT = 10;

function frameColumn(frame: number | string): number {
  const numericFrame = typeof frame === "number" ? frame : Number.parseInt(frame, 10);
  if (!Number.isFinite(numericFrame)) return 0;
  return ((Math.trunc(numericFrame) % WALK_FRAMES_PER_DIRECTION) + WALK_FRAMES_PER_DIRECTION)
    % WALK_FRAMES_PER_DIRECTION;
}

export function frameBottomPadding(frame: number | string): number {
  return FRAME_BOTTOM_PADDING[frameColumn(frame)];
}

export function groundedSpriteY(frame: number | string, renderedScale: number): number {
  return frameBottomPadding(frame) * renderedScale;
}

export function visibleFootY(frame: number | string, renderedScale: number, spriteY: number): number {
  return spriteY - frameBottomPadding(frame) * renderedScale;
}
