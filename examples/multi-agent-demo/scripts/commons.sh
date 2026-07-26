#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"
demo_root="$(cd "$script_dir/.." && pwd)"
demo_home="$demo_root/.demo_state/commons-home"

mkdir -p "$demo_home"

COMMONS_HOME="$demo_home" \
  PYTHONPATH="$repo_root${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m commons.cli "$@"
