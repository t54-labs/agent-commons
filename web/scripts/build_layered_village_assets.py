#!/usr/bin/env python3
"""Build trimmed transparent sprites for the layered Commons village."""

from __future__ import annotations

import math
from pathlib import Path
from statistics import median

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "assets-source" / "village" / "layered-v3"
OUTPUT_DIR = ROOT / "public" / "village" / "layered-v3"

SPRITES = {
    "workstation-warm": (250, 205),
    "workstation-light": (250, 205),
    "workstation-dark": (250, 205),
    "storage-tech": (250, 125),
    "storage-studio": (270, 130),
    "central-garden": (260, 210),
    "path-lamp": (64, 120),
}


def sample_key(image: Image.Image) -> tuple[int, int, int]:
    width, height = image.size
    samples: list[tuple[int, int, int]] = []
    margin = max(2, min(width, height) // 80)
    for y in (*range(margin), *range(height - margin, height)):
        for x in range(0, width, max(1, width // 64)):
            samples.append(image.getpixel((x, y))[:3])
    for x in (*range(margin), *range(width - margin, width)):
        for y in range(0, height, max(1, height // 64)):
            samples.append(image.getpixel((x, y))[:3])
    return tuple(int(median(channel)) for channel in zip(*samples))


def remove_chroma(image: Image.Image) -> Image.Image:
    source = image.convert("RGB")
    key = sample_key(source)
    output = Image.new("RGBA", source.size)
    converted = []
    pixel_data = source.get_flattened_data() if hasattr(source, "get_flattened_data") else source.getdata()
    for red, green, blue in pixel_data:
        distance = math.sqrt((red - key[0]) ** 2 + (green - key[1]) ** 2 + (blue - key[2]) ** 2)
        if distance <= 18:
            alpha = 0
        elif distance >= 76:
            alpha = 255
        else:
            alpha = round((distance - 18) / 58 * 255)
        if alpha < 255:
            magenta_excess = max(0, min(red, blue) - green)
            red = max(0, red - round(magenta_excess * (1 - alpha / 255)))
            blue = max(0, blue - round(magenta_excess * (1 - alpha / 255)))
        converted.append((red, green, blue, alpha))
    output.putdata(converted)
    return output


def trim_and_resize(image: Image.Image, bounds: tuple[int, int]) -> Image.Image:
    alpha = image.getchannel("A")
    crop = alpha.getbbox()
    if crop is None:
        raise ValueError("Generated sprite contains no opaque pixels")
    trimmed = image.crop(crop)
    maximum_width, maximum_height = bounds
    scale = min(maximum_width / trimmed.width, maximum_height / trimmed.height)
    target = (max(1, round(trimmed.width * scale)), max(1, round(trimmed.height * scale)))
    return trimmed.resize(target, Image.Resampling.NEAREST)


def validate_sprite(name: str, sprite: Image.Image) -> None:
    alpha = sprite.getchannel("A")
    pixels = list(alpha.get_flattened_data() if hasattr(alpha, "get_flattened_data") else alpha.getdata())
    transparent_ratio = sum(value == 0 for value in pixels) / len(pixels)
    if transparent_ratio < 0.08:
        raise ValueError(f"{name} still contains an opaque rectangular background")
    if any(alpha.getpixel(point) != 0 for point in ((0, 0), (sprite.width - 1, 0), (0, sprite.height - 1), (sprite.width - 1, sprite.height - 1))):
        raise ValueError(f"{name} must keep transparent corners")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, bounds in SPRITES.items():
        source = Image.open(SOURCE_DIR / f"{name}-chroma.png")
        sprite = trim_and_resize(remove_chroma(source), bounds)
        validate_sprite(name, sprite)
        output_path = OUTPUT_DIR / f"{name}.png"
        sprite.save(output_path, optimize=True)
        print(f"Built {output_path.relative_to(ROOT)} ({sprite.width}x{sprite.height})")


if __name__ == "__main__":
    main()
