#!/usr/bin/env python3
"""Validate release identity, onboarding pins, and Python distributions."""

from __future__ import annotations

import argparse
import email.parser
import re
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PINNED_ONBOARDING_FILES = (
    ROOT / "README.md",
    ROOT / "PYPI.md",
    ROOT / "docs" / "getting-started.md",
    ROOT / "docs" / "team-onboarding.md",
    ROOT / "scripts" / "install.sh",
    ROOT / ".agents" / "skills" / "commons" / "SKILL.md",
    ROOT / "commons" / "skill_template" / "SKILL.md",
)
REQUIRED_PROJECT_URLS = {"Homepage", "Documentation", "Repository", "Issues", "Changelog"}
CANONICAL_REPOSITORY = "https://github.com/t54-labs/agent-commons"
EXPECTED_PROJECT_URLS = {
    "Homepage": CANONICAL_REPOSITORY,
    "Documentation": f"{CANONICAL_REPOSITORY}/tree/main/docs",
    "Repository": f"{CANONICAL_REPOSITORY}.git",
    "Issues": f"{CANONICAL_REPOSITORY}/issues",
    "Changelog": f"{CANONICAL_REPOSITORY}/blob/main/CHANGELOG.md",
}


def project_metadata() -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]


def module_version() -> str:
    text = (ROOT / "commons" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise ValueError("commons/__init__.py does not define __version__")
    return match.group(1)


def parse_metadata(text: str) -> email.message.Message:
    return email.parser.Parser().parsestr(text)


def validate_core_metadata(metadata: email.message.Message, version: str, label: str) -> list[str]:
    failures: list[str] = []
    if metadata.get("Name") != "agent-commons":
        failures.append(f"{label}: Name must be agent-commons")
    if metadata.get("Version") != version:
        failures.append(f"{label}: Version must be {version}")
    if metadata.get("License-Expression") != "Apache-2.0":
        failures.append(f"{label}: License-Expression must be Apache-2.0")
    project_urls = {
        value.split(",", 1)[0].strip(): value.split(",", 1)[1].strip()
        for value in metadata.get_all("Project-URL", [])
        if "," in value
    }
    missing_urls = sorted(REQUIRED_PROJECT_URLS - set(project_urls))
    if missing_urls:
        failures.append(f"{label}: missing Project-URL labels: {', '.join(missing_urls)}")
    for name, expected in EXPECTED_PROJECT_URLS.items():
        if name in project_urls and project_urls[name] != expected:
            failures.append(f"{label}: {name} URL must be {expected}")
    return failures


def validate_source(tag: str | None) -> tuple[str, list[str]]:
    failures: list[str] = []
    project = project_metadata()
    version = str(project["version"])
    if project.get("name") != "agent-commons":
        failures.append("pyproject.toml: project.name must be agent-commons")
    if module_version() != version:
        failures.append("pyproject.toml and commons.__version__ differ")
    urls = project.get("urls")
    if not isinstance(urls, dict):
        failures.append("pyproject.toml: project.urls is required")
    else:
        missing_urls = sorted(REQUIRED_PROJECT_URLS - set(urls))
        if missing_urls:
            failures.append(f"pyproject.toml: missing project URLs: {', '.join(missing_urls)}")
        for name, expected in EXPECTED_PROJECT_URLS.items():
            if urls.get(name) != expected:
                failures.append(f"pyproject.toml: {name} URL must be {expected}")

    if tag:
        expected_tag = f"v{version}"
        if tag != expected_tag:
            failures.append(f"release tag {tag!r} must equal {expected_tag!r}")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        if f"## [{version}]" not in changelog:
            failures.append(f"CHANGELOG.md: missing release heading for {version}")
        expected_pin = f"agent-commons=={version}"
        for path in PINNED_ONBOARDING_FILES:
            if expected_pin not in path.read_text(encoding="utf-8"):
                failures.append(f"{path.relative_to(ROOT)}: missing release pin {expected_pin}")

    return version, failures


def validate_wheel(path: Path, version: str) -> list[str]:
    failures: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            return [f"{path.name}: expected one wheel METADATA file"]
        metadata = parse_metadata(archive.read(metadata_names[0]).decode("utf-8"))
        failures.extend(validate_core_metadata(metadata, version, path.name))
        required_suffixes = (
            "commons/cline_template/commons-bootstrap.md",
            "commons/skill_template/SKILL.md",
            ".dist-info/licenses/LICENSE",
            ".dist-info/licenses/NOTICE",
        )
        for suffix in required_suffixes:
            if not any(name.endswith(suffix) for name in names):
                failures.append(f"{path.name}: missing {suffix}")
    return failures


def validate_sdist(path: Path, version: str) -> list[str]:
    failures: list[str] = []
    with tarfile.open(path, "r:gz") as archive:
        names = archive.getnames()
        metadata_names = [name for name in names if name.count("/") == 1 and name.endswith("/PKG-INFO")]
        if len(metadata_names) != 1:
            return [f"{path.name}: expected one root PKG-INFO file"]
        member = archive.extractfile(metadata_names[0])
        if member is None:
            return [f"{path.name}: cannot read PKG-INFO"]
        metadata = parse_metadata(member.read().decode("utf-8"))
        failures.extend(validate_core_metadata(metadata, version, path.name))
        required_suffixes = (
            "/LICENSE",
            "/NOTICE",
            "/commons/cline_template/commons-bootstrap.md",
            "/commons/skill_template/SKILL.md",
        )
        for suffix in required_suffixes:
            if not any(name.endswith(suffix) for name in names):
                failures.append(f"{path.name}: missing {suffix.lstrip('/')}")
    return failures


def validate_distributions(dist_dir: Path, version: str) -> list[str]:
    failures: list[str] = []
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1:
        failures.append(f"{dist_dir}: expected one wheel, found {len(wheels)}")
    else:
        failures.extend(validate_wheel(wheels[0], version))
    if len(sdists) != 1:
        failures.append(f"{dist_dir}: expected one sdist, found {len(sdists)}")
    else:
        failures.extend(validate_sdist(sdists[0], version))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="release tag, for example v0.3.1")
    parser.add_argument("--dist-dir", type=Path, help="directory containing one wheel and one sdist")
    args = parser.parse_args()

    try:
        version, failures = validate_source(args.tag)
        if args.dist_dir:
            failures.extend(validate_distributions(args.dist_dir, version))
    except (KeyError, OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
        failures = [str(exc)]
        version = "unknown"

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    scope = "source and distributions" if args.dist_dir else "source"
    print(f"Release checks passed for {scope}: agent-commons {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
