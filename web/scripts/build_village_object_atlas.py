#!/usr/bin/env python3
"""Build the Phaser foreground-object atlas from the village source map."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


WEB_ROOT = Path(__file__).resolve().parents[1]
LEVEL_PATH = WEB_ROOT / "assets-source" / "village" / "level.json"
MAP_PATH = WEB_ROOT / "public" / "village" / "commons-village-map-v2.png"
OUTPUT_DIR = WEB_ROOT / "public" / "village" / "objects"
ATLAS_IMAGE_PATH = OUTPUT_DIR / "atlas.png"
ATLAS_DATA_PATH = OUTPUT_DIR / "atlas.json"
ATLAS_MAX_WIDTH = 1024
ATLAS_PADDING = 2


def load_level() -> dict:
    with LEVEL_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def point_in_polygon(point: tuple[float, float], polygon: list[list[int]]) -> bool:
    x, y = point
    inside = False
    previous = len(polygon) - 1
    for current, current_point in enumerate(polygon):
        current_x, current_y = current_point
        previous_x, previous_y = polygon[previous]
        crosses = (current_y > y) != (previous_y > y) and x < (
            (previous_x - current_x) * (y - current_y)
            / (previous_y - current_y or float.fromhex("0x1.0p-52"))
            + current_x
        )
        if crosses:
            inside = not inside
        previous = current
    return inside


def foot_point_is_blocked(level: dict, point: tuple[float, float], radius: float = 8) -> bool:
    x, y = point
    samples = [
        (x, y),
        (x - radius, y),
        (x + radius, y),
        (x, y - radius * 0.45),
        (x, y + radius * 0.45),
    ]
    return any(
        point_in_polygon(sample, polygon)
        for object_config in level["objects"]
        for polygon in object_config["collision_polygons"]
        for sample in samples
    )


def point_is_walkable(level: dict, point: tuple[float, float], radius: float = 8) -> bool:
    inside_walkable_area = any(
        point_in_polygon(point, polygon)
        for polygon in level["navigation"]["walkable_polygons"]
    )
    return inside_walkable_area and not foot_point_is_blocked(level, point, radius)


def segment_is_walkable(level: dict, start: list[int], end: list[int]) -> bool:
    distance = math.hypot(end[0] - start[0], end[1] - start[1])
    sample_count = max(1, math.ceil(distance / 6))
    for index in range(sample_count + 1):
        progress = index / sample_count
        point = (
            start[0] + (end[0] - start[0]) * progress,
            start[1] + (end[1] - start[1]) * progress,
        )
        if foot_point_is_blocked(level, point):
            return False
    return True


def validate_level(level: dict) -> None:
    map_size = (level["map"]["width"], level["map"]["height"])
    issues: list[str] = []
    loop = level["navigation"]["central_loop"]
    objects_by_id = {object_config["id"]: object_config for object_config in level["objects"]}
    required_kinds = {"workstation", "landscape", "lamp", "boundary", "storage", "bridge", "sign", "tree"}
    present_kinds = {object_config["kind"] for object_config in level["objects"]}
    missing_kinds = sorted(required_kinds - present_kinds)
    if missing_kinds:
        issues.append(f"object manifest is missing semantic kinds: {', '.join(missing_kinds)}")
    required_station_layers = {
        "northwest": {"northwest-table-chairs", "northwest-rear-structure", "northwest-front-rail"},
        "north": {"north-table-chairs", "north-rear-structure", "north-front-rail"},
        "northeast": {"northeast-table-chairs", "northeast-rear-structure", "northeast-front-wall"},
        "southwest": {"southwest-table-chairs", "southwest-rear-structure", "southwest-front-rail"},
        "south": {"south-table-chairs", "south-rear-structure", "south-front-wall"},
        "southeast": {"southeast-table-chairs", "southeast-rear-structure", "southeast-front-wall"},
    }
    for station_id, required_ids in required_station_layers.items():
        missing_ids = sorted(required_ids - objects_by_id.keys())
        if missing_ids:
            issues.append(f"{station_id} is missing world layers: {', '.join(missing_ids)}")
    required_bridge_layers = {
        "west-bridge-back-rail", "west-bridge-front-rail",
        "red-bridge-back-rail", "red-bridge-front-rail",
        "east-bridge-back-rail", "east-bridge-front-rail",
    }
    missing_bridge_layers = sorted(required_bridge_layers - objects_by_id.keys())
    if missing_bridge_layers:
        issues.append(f"bridges are missing split rails: {', '.join(missing_bridge_layers)}")

    garden_ground = objects_by_id.get("central-garden-ground")
    garden_occluder = objects_by_id.get("central-garden-occluder")
    if not garden_ground or not garden_occluder:
        issues.append("central garden must have separate ground and occluder layers")
    else:
        if garden_ground.get("render_layer") != "ground" or garden_occluder.get("render_layer") != "world":
            issues.append("central garden layers use the wrong render order")
        garden_depth_y = garden_occluder["depth_y"]
        if not any(point[1] < garden_depth_y for point in loop):
            issues.append("central loop has no route behind the garden occluder")
        if not any(point[1] > garden_depth_y for point in loop):
            issues.append("central loop has no route in front of the garden occluder")
        road_samples = [(8, 112), (267, 112), (138, 8), (138, 220)]
        for object_config in (garden_ground, garden_occluder):
            if any(
                point_in_polygon(sample, polygon)
                for sample in road_samples
                for polygon in object_config["mask_polygons"]
            ):
                issues.append(f"{object_config['id']} mask includes outer stone-path pixels")

    for object_config in level["objects"]:
        crop_x, crop_y, width, height = object_config["crop"]
        if crop_x < 0 or crop_y < 0 or crop_x + width > map_size[0] or crop_y + height > map_size[1]:
            issues.append(f"{object_config['id']} crop exceeds the map")
        if not object_config["mask_polygons"]:
            issues.append(f"{object_config['id']} has no visual mask")
        if object_config.get("render_layer", "world") == "world" and not crop_y <= object_config["depth_y"] <= crop_y + height:
            issues.append(f"{object_config['id']} depth pivot is outside its crop")
        for polygon in object_config["mask_polygons"]:
            if any(x < 0 or y < 0 or x > width or y > height for x, y in polygon):
                issues.append(f"{object_config['id']} visual mask exceeds its crop")
        for polygon in object_config["collision_polygons"]:
            if any(x < 0 or y < 0 or x > map_size[0] or y > map_size[1] for x, y in polygon):
                issues.append(f"{object_config['id']} collision exceeds the map")

    for station in level["stations"]:
        for slot_index, slot in enumerate(station["agent_slots"]):
            if foot_point_is_blocked(level, tuple(slot)):
                issues.append(f"{station['id']} Agent slot {slot_index} intersects a collision body")

    cell_size = level["navigation"]["cell_size"]
    grid_width = math.ceil(map_size[0] / cell_size)
    grid_height = math.ceil(map_size[1] / cell_size)
    walkable_cells = {
        (x, y)
        for y in range(grid_height)
        for x in range(grid_width)
        if point_is_walkable(
            level,
            (
                min(map_size[0] - 1, x * cell_size + cell_size / 2),
                min(map_size[1] - 1, y * cell_size + cell_size / 2),
            ),
        )
    }
    if not walkable_cells:
        issues.append("navigation grid has no walkable cells")
    else:
        unseen = set(walkable_cells)
        components: list[set[tuple[int, int]]] = []
        while unseen:
            component = {unseen.pop()}
            frontier = list(component)
            while frontier:
                x, y = frontier.pop()
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    neighbor = (x + dx, y + dy)
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        component.add(neighbor)
                        frontier.append(neighbor)
            components.append(component)
        largest_component = max(components, key=len)
        coverage = len(largest_component) / len(walkable_cells)
        if coverage < 0.9:
            issues.append(f"navigation grid is fragmented; largest component covers only {coverage:.1%}")
        if len(largest_component) < 500:
            issues.append("navigation grid is too small for varied random destinations")

    if issues:
        raise SystemExit("Village level validation failed:\n- " + "\n- ".join(issues))


def extract_objects(level: dict, source: Image.Image) -> list[tuple[dict, Image.Image]]:
    extracted: list[tuple[dict, Image.Image]] = []
    for object_config in level["objects"]:
        crop_x, crop_y, width, height = object_config["crop"]
        cutout = source.crop((crop_x, crop_y, crop_x + width, crop_y + height)).convert("RGBA")
        alpha = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(alpha)
        for polygon in object_config["mask_polygons"]:
            draw.polygon([tuple(point) for point in polygon], fill=255)
        cutout.putalpha(alpha)
        extracted.append((object_config, cutout))
    return extracted


def pack_objects(objects: list[tuple[dict, Image.Image]]) -> tuple[Image.Image, dict]:
    placements: list[tuple[dict, Image.Image, int, int]] = []
    cursor_x = ATLAS_PADDING
    cursor_y = ATLAS_PADDING
    row_height = 0
    used_width = 0

    for object_config, cutout in objects:
        width, height = cutout.size
        if cursor_x + width + ATLAS_PADDING > ATLAS_MAX_WIDTH and cursor_x > ATLAS_PADDING:
            cursor_x = ATLAS_PADDING
            cursor_y += row_height + ATLAS_PADDING
            row_height = 0
        placements.append((object_config, cutout, cursor_x, cursor_y))
        cursor_x += width + ATLAS_PADDING
        row_height = max(row_height, height)
        used_width = max(used_width, cursor_x)

    atlas_width = min(ATLAS_MAX_WIDTH, max(2, used_width + ATLAS_PADDING))
    atlas_height = cursor_y + row_height + ATLAS_PADDING
    atlas = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))
    frames: dict[str, dict] = {}

    for object_config, cutout, x, y in placements:
        width, height = cutout.size
        atlas.alpha_composite(cutout, (x, y))
        frames[object_config["id"]] = {
            "frame": {"x": x, "y": y, "w": width, "h": height},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": width, "h": height},
            "sourceSize": {"w": width, "h": height},
        }

    data = {
        "frames": frames,
        "meta": {
            "app": "Commons village object-atlas builder",
            "version": "1",
            "image": ATLAS_IMAGE_PATH.name,
            "format": "RGBA8888",
            "size": {"w": atlas_width, "h": atlas_height},
            "scale": "1",
        },
    }
    return atlas, data


def main() -> None:
    level = load_level()
    validate_level(level)
    source = Image.open(MAP_PATH).convert("RGBA")
    expected_size = (level["map"]["width"], level["map"]["height"])
    if source.size != expected_size:
        raise SystemExit(f"Village map is {source.size}, expected {expected_size}")

    atlas, data = pack_objects(extract_objects(level, source))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    atlas.save(ATLAS_IMAGE_PATH, optimize=True)
    ATLAS_DATA_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Built {len(data['frames'])} object frames in {ATLAS_IMAGE_PATH}")


if __name__ == "__main__":
    main()
