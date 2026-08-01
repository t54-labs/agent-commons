#!/usr/bin/env python3
"""Render navigation, collision, sprite bounds, and Agent slots for village v3."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
LEVEL_PATH = ROOT / "assets-source" / "village" / "level-v3.json"
PUBLIC_DIR = ROOT / "public"
OUTPUT_PATH = ROOT / "test-results" / "village-layered-debug.png"


def point_in_polygon(point: tuple[float, float], polygon: list[list[int]]) -> bool:
    x, y = point
    inside = False
    previous = len(polygon) - 1
    for current, (current_x, current_y) in enumerate(polygon):
        previous_x, previous_y = polygon[previous]
        crosses = (current_y > y) != (previous_y > y) and x < (
            (previous_x - current_x) * (y - current_y) / (previous_y - current_y or 1e-9) + current_x
        )
        if crosses:
            inside = not inside
        previous = current
    return inside


def main() -> None:
    level = json.loads(LEVEL_PATH.read_text())
    base = Image.open(PUBLIC_DIR / level["map"]["asset"]).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    for polygon in level["navigation"]["walkable_polygons"]:
        draw.polygon([tuple(point) for point in polygon], fill=(56, 221, 151, 42), outline=(56, 221, 151, 210), width=2)

    collision_polygons: list[list[list[int]]] = []
    for item in level["objects"]:
        sprite = Image.open(PUBLIC_DIR / item["asset"])
        x, y = item["position"]
        left = round(x - sprite.width / 2)
        top = y - sprite.height
        draw.rectangle((left, top, left + sprite.width, y), outline=(255, 214, 92, 235), width=2)
        draw.ellipse((x - 4, item["depth_y"] - 4, x + 4, item["depth_y"] + 4), fill=(255, 214, 92, 255))
        draw.text((left + 3, top + 3), item["id"], fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(18, 43, 43, 255))
        for polygon in item["collision_polygons"]:
            collision_polygons.append(polygon)
            draw.polygon([tuple(point) for point in polygon], fill=(255, 80, 80, 70), outline=(255, 80, 80, 235), width=2)

    for boundary in level["boundaries"]:
        for polygon in boundary["collision_polygons"]:
            collision_polygons.append(polygon)
            draw.polygon([tuple(point) for point in polygon], fill=(255, 63, 92, 92), outline=(255, 63, 92, 255), width=3)

    for portal in level["portals"]:
        inside = tuple(portal["inside"])
        outside = tuple(portal["outside"])
        draw.line((inside, outside), fill=(83, 255, 211, 255), width=5)
        draw.ellipse((inside[0] - 6, inside[1] - 6, inside[0] + 6, inside[1] + 6), fill=(83, 255, 211, 255))
        draw.ellipse((outside[0] - 6, outside[1] - 6, outside[0] + 6, outside[1] + 6), fill=(83, 255, 211, 255))

    blocked_slots = []
    for station in level["stations"]:
        for slot in station["agent_slots"]:
            clearance_samples = (
                tuple(slot),
                (slot[0] - 8, slot[1]),
                (slot[0] + 8, slot[1]),
                (slot[0], slot[1] - 3.6),
                (slot[0], slot[1] + 3.6),
            )
            blocked = any(
                point_in_polygon(sample, polygon)
                for polygon in collision_polygons
                for sample in clearance_samples
            )
            color = (255, 80, 80, 255) if blocked else (105, 202, 255, 255)
            draw.ellipse((slot[0] - 5, slot[1] - 5, slot[0] + 5, slot[1] + 5), fill=color)
            if blocked:
                blocked_slots.append((station["id"], slot))

    if blocked_slots:
        raise ValueError(f"Agent slots intersect collisions: {blocked_slots}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(base, overlay).save(OUTPUT_PATH, optimize=True)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
