#!/usr/bin/env python3
"""Render walkable areas, collision bodies, and object depth pivots for review."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw


WEB_ROOT = Path(__file__).resolve().parents[1]
LEVEL_PATH = WEB_ROOT / "assets-source" / "village" / "level.json"
MAP_PATH = WEB_ROOT / "public" / "village" / "commons-village-map-v2.png"
DEFAULT_OUTPUT = WEB_ROOT / "test-results" / "village-level-debug.png"


def main() -> None:
    output = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_OUTPUT
    level = json.loads(LEVEL_PATH.read_text(encoding="utf-8"))
    canvas = Image.open(MAP_PATH).convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    for polygon in level["navigation"]["walkable_polygons"]:
        points = [tuple(point) for point in polygon]
        draw.polygon(points, fill=(45, 220, 155, 34), outline=(75, 255, 185, 190), width=2)

    for object_config in level["objects"]:
        crop_x, crop_y, _, _ = object_config["crop"]
        color = (255, 217, 86, 220) if object_config.get("render_layer", "world") == "world" else (80, 180, 255, 220)
        for polygon in object_config["mask_polygons"]:
            points = [(crop_x + x, crop_y + y) for x, y in polygon]
            draw.line([*points, points[0]], fill=color, width=2)
        for polygon in object_config["collision_polygons"]:
            points = [tuple(point) for point in polygon]
            draw.polygon(points, fill=(255, 70, 70, 70), outline=(255, 70, 70, 240), width=2)
        depth_y = object_config["depth_y"]
        depth_x = crop_x + 8
        draw.line((depth_x, depth_y, depth_x + 34, depth_y), fill=(255, 255, 255, 230), width=2)
        draw.text((depth_x + 38, depth_y - 6), object_config["id"], fill=(255, 255, 255, 245), stroke_width=2, stroke_fill=(0, 0, 0, 220))

    output.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(canvas, overlay).save(output)
    print(output)


if __name__ == "__main__":
    main()
