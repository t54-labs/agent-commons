#!/usr/bin/env python3
"""Validate public documentation links and publication hygiene."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
PRIVATE_PATH_PATTERNS = (
    re.compile(r"/Users/(?!you(?:/|$)|example(?:/|$))[A-Za-z0-9._-]+"),
    re.compile(r"/home/(?!user(?:/|$)|example(?:/|$))[A-Za-z0-9._-]+"),
    re.compile(r"file://(?:/Users|/home)/"),
)


def markdown_files() -> list[Path]:
    files = [
        ROOT / "README.md",
        ROOT / "PYPI.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "SECURITY.md",
        ROOT / "GOVERNANCE.md",
        ROOT / "CODE_OF_CONDUCT.md",
    ]
    files.extend(sorted((ROOT / "docs").rglob("*.md")))
    files.extend(sorted((ROOT / "examples").rglob("*.md")))
    files.extend(sorted((ROOT / ".agents" / "skills").rglob("*.md")))
    return [path for path in files if path.exists()]


def check_links(paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            target = match.group(1).strip().strip("<>").split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            candidate = (path.parent / target).resolve()
            try:
                candidate.relative_to(ROOT)
            except ValueError:
                failures.append(f"{path.relative_to(ROOT)}: link escapes repository: {target}")
                continue
            if not candidate.exists():
                failures.append(f"{path.relative_to(ROOT)}: missing link target: {target}")
    return failures


def check_public_paths(paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for pattern in PRIVATE_PATH_PATTERNS:
            match = pattern.search(text)
            if match:
                failures.append(
                    f"{path.relative_to(ROOT)}: non-placeholder absolute path: {match.group(0)}"
                )
    return failures


def check_skill_sync() -> list[str]:
    source = ROOT / ".agents" / "skills" / "commons" / "SKILL.md"
    packaged = ROOT / "commons" / "skill_template" / "SKILL.md"
    if source.read_bytes() != packaged.read_bytes():
        return ["Commons Skill source and packaged template differ"]
    return []


def main() -> int:
    paths = markdown_files()
    failures = [
        *check_links(paths),
        *check_public_paths(paths),
        *check_skill_sync(),
    ]
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print(f"Documentation checks passed for {len(paths)} Markdown files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
