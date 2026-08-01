from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
FRONT_DIR = ROOT / "public" / "village" / "agents"
LEFT_ATLAS = ROOT / "assets-source" / "village" / "agents-left.png"
UP_ATLAS = ROOT / "assets-source" / "village" / "agents-up.png"
OUTPUT_DIR = ROOT / "public" / "village" / "walk"

ROWS = 3
COLUMNS = 4
AGENT_COUNT = ROWS * COLUMNS
FRAME_WIDTH = 64
FRAME_HEIGHT = 80
CONTENT_WIDTH = 56
CONTENT_HEIGHT = 72
DIRECTIONS = ("down", "left", "right", "up")


def normalize_sprite(sprite: Image.Image) -> Image.Image:
    sprite = sprite.convert("RGBA")
    bounds = sprite.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("sprite has no visible pixels")
    sprite = sprite.crop(bounds)
    scale = min(CONTENT_WIDTH / sprite.width, CONTENT_HEIGHT / sprite.height)
    size = (max(1, round(sprite.width * scale)), max(1, round(sprite.height * scale)))
    sprite = sprite.resize(size, Image.Resampling.NEAREST)
    frame = Image.new("RGBA", (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0, 0))
    frame.alpha_composite(sprite, ((FRAME_WIDTH - size[0]) // 2, FRAME_HEIGHT - size[1] - 2))
    return frame


def split_atlas(path: Path) -> list[Image.Image]:
    atlas = Image.open(path).convert("RGBA")
    sprites: list[Image.Image] = []
    for row in range(ROWS):
        for column in range(COLUMNS):
            left = round(column * atlas.width / COLUMNS)
            right = round((column + 1) * atlas.width / COLUMNS)
            top = round(row * atlas.height / ROWS)
            bottom = round((row + 1) * atlas.height / ROWS)
            sprites.append(normalize_sprite(atlas.crop((left, top, right, bottom))))
    return sprites


def composite_part(frame: Image.Image, part: Image.Image, x: int, y: int) -> None:
    frame.alpha_composite(part, (x, y))


def walk_frames(base: Image.Image, *, side_view: bool) -> list[Image.Image]:
    alpha_bounds = base.getchannel("A").getbbox()
    if alpha_bounds is None:
        return [base.copy() for _ in range(4)]
    left, top, right, bottom = alpha_bounds
    center = (left + right) // 2
    leg_top = max(top + 16, bottom - 21)
    overlap = 2

    upper = base.crop((0, 0, FRAME_WIDTH, leg_top + overlap))
    left_leg = base.crop((0, leg_top - overlap, center + overlap, FRAME_HEIGHT))
    right_leg = base.crop((center - overlap, leg_top - overlap, FRAME_WIDTH, FRAME_HEIGHT))

    poses = (
        (0, 0, 0, 0, 0),
        (-1, -1, 1, 1, -2),
        (-2, 0, -1, 0, -1),
        (-1, -1, -2, 1, 1),
    )
    frames: list[Image.Image] = []
    for frame_index, (body_y, left_x, left_y, right_x, right_y) in enumerate(poses):
        frame = Image.new("RGBA", (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0, 0))
        body_x = (frame_index - 2) if side_view and frame_index in {1, 3} else 0
        composite_part(frame, upper, body_x, body_y)
        composite_part(frame, left_leg, left_x + body_x, leg_top - overlap + left_y)
        composite_part(frame, right_leg, center - overlap + right_x + body_x, leg_top - overlap + right_y)
        frames.append(frame)
    return frames


def build_sheet(front: Image.Image, left: Image.Image, up: Image.Image) -> Image.Image:
    direction_sources = {
        "down": front,
        "left": left,
        "right": ImageOps.mirror(left),
        "up": up,
    }
    sheet = Image.new(
        "RGBA",
        (FRAME_WIDTH * 4, FRAME_HEIGHT * len(DIRECTIONS)),
        (0, 0, 0, 0),
    )
    for row, direction in enumerate(DIRECTIONS):
        frames = walk_frames(direction_sources[direction], side_view=direction in {"left", "right"})
        for column, frame in enumerate(frames):
            sheet.alpha_composite(frame, (column * FRAME_WIDTH, row * FRAME_HEIGHT))
    return sheet


def main() -> None:
    left_sprites = split_atlas(LEFT_ATLAS)
    up_sprites = split_atlas(UP_ATLAS)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for index in range(AGENT_COUNT):
        front = Image.open(FRONT_DIR / f"agent-{index:02d}.png").convert("RGBA")
        sheet = build_sheet(front, left_sprites[index], up_sprites[index])
        sheet.save(OUTPUT_DIR / f"agent-{index:02d}.png", optimize=True)


if __name__ == "__main__":
    main()
