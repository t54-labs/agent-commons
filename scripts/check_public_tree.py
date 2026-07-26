#!/usr/bin/env python3
"""Fail when a tracked public tree contains common private release hazards."""

from __future__ import annotations

import argparse
import ipaddress
import re
import subprocess
import sys
from pathlib import Path


SENSITIVE_FILE_PATTERNS = (
    re.compile(r"(^|/)\.env(?:\.|$)"),
    re.compile(r"(^|/)\.pypirc$"),
    re.compile(r"(^|/)(?:id_rsa|id_ed25519)$"),
    re.compile(r"\.(?:pem|key|p12|pfx|token|db|sqlite|sqlite3)$", re.IGNORECASE),
    re.compile(r"(^|/)(?:credentials?|secrets?)[^/]*\.json$", re.IGNORECASE),
    re.compile(r"(^|/)\.commons/"),
)
CONTENT_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{12,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_-]{20,}")),
    (
        "OpenAI-style key",
        re.compile(r"(?:sk-(?:proj|admin|svcacct)-[A-Za-z0-9_-]{16,}|sk-[A-Za-z0-9]{32,})"),
    ),
    ("credential-bearing URL", re.compile(r"https?://[^\s/:]+:[^\s/@]+@")),
    (
        "assigned credential",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{12,}"
        ),
    ),
)
ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"/Users/(?!you(?:/|$)|example(?:/|$))[A-Za-z0-9._-]+"),
    re.compile(r"/home/(?!user(?:/|$)|example(?:/|$))[A-Za-z0-9._-]+"),
    re.compile(r"file://(?:/Users|/home)/"),
)
IPV4 = re.compile(r"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])")
SELF_PATHS = {"scripts/check_public_tree.py", "scripts/check_docs.py"}


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    return [root / item.decode("utf-8") for item in output.split(b"\0") if item]


def allowed_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return True
    documentation_ranges = (
        ipaddress.ip_network("192.0.2.0/24"),
        ipaddress.ip_network("198.51.100.0/24"),
        ipaddress.ip_network("203.0.113.0/24"),
    )
    return address.is_loopback or address.is_unspecified or any(address in network for network in documentation_ranges)


def scan(root: Path) -> list[str]:
    failures: list[str] = []
    files = tracked_files(root)
    for path in files:
        relative = path.relative_to(root).as_posix()
        for pattern in SENSITIVE_FILE_PATTERNS:
            if pattern.search(relative) and not relative.endswith(".env.example"):
                failures.append(f"{relative}: sensitive filename must not be tracked")
                break

        if relative in SELF_PATHS:
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            failures.append(f"{relative}: cannot read tracked file: {exc}")
            continue
        text = data.decode("utf-8", errors="ignore")
        for label, pattern in CONTENT_PATTERNS:
            if pattern.search(text):
                failures.append(f"{relative}: possible {label}")
        for pattern in ABSOLUTE_PATH_PATTERNS:
            match = pattern.search(text)
            if match:
                failures.append(f"{relative}: non-placeholder absolute path {match.group(0)}")
        for value in set(IPV4.findall(text)):
            if not allowed_ip(value):
                failures.append(f"{relative}: non-documentation IPv4 address {value}")

    if not (root / "LICENSE").is_file():
        failures.append("LICENSE: required public file is missing")
    if not (root / "NOTICE").is_file():
        failures.append("NOTICE: required public file is missing")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    try:
        failures = scan(root)
        count = len(tracked_files(root))
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: unable to inspect public tree: {exc}", file=sys.stderr)
        return 1
    if failures:
        for failure in sorted(set(failures)):
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print(f"Public tree checks passed for {count} tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
