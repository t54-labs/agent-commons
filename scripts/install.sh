#!/usr/bin/env bash
set -euo pipefail

source_ref="${COMMONS_INSTALL_SOURCE:-agent-commons==0.5.0}"
target="all"
scope="user"
project_dir=""
commons_home="${COMMONS_HOME:-$HOME/.commons}"
python_bin="${PYTHON_BIN:-python3}"

usage() {
  cat <<'EOF'
Install Commons into an isolated virtual environment and install its Agent Skill.

Usage:
  ./scripts/install.sh [options]

Options:
  --source <path-or-pip-ref>  Package source (default: agent-commons==0.5.0 from PyPI)
  --target <all|both|codex|claude|cline>
  --scope <user|project>
  --project-dir <path>        Destination project for project-scoped Skills
  --commons-home <path>       Commons state and virtual environment root
  --python <executable>       Python 3.11+ executable
  -h, --help

Examples:
  ./scripts/install.sh
  ./scripts/install.sh --source .
  ./scripts/install.sh --source agent-commons
  ./scripts/install.sh --target codex
  ./scripts/install.sh --source . --scope project --project-dir "$PWD"
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      source_ref="${2:?--source requires a value}"
      shift 2
      ;;
    --target)
      target="${2:?--target requires a value}"
      shift 2
      ;;
    --scope)
      scope="${2:?--scope requires a value}"
      shift 2
      ;;
    --project-dir)
      project_dir="${2:?--project-dir requires a value}"
      shift 2
      ;;
    --commons-home)
      commons_home="${2:?--commons-home requires a value}"
      shift 2
      ;;
    --python)
      python_bin="${2:?--python requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$target" in
  all|both|codex|claude|cline) ;;
  *)
    echo "--target must be all, both, codex, claude, or cline" >&2
    exit 2
    ;;
esac

case "$scope" in
  user|project) ;;
  *)
    echo "--scope must be user or project" >&2
    exit 2
    ;;
esac

if [[ -d "$source_ref" ]]; then
  source_ref="$(cd "$source_ref" && pwd -P)"
elif [[ -f "$source_ref" ]]; then
  source_ref="$(cd "$(dirname "$source_ref")" && pwd -P)/$(basename "$source_ref")"
fi

"$python_bin" - <<'PY'
import sys

if sys.version_info < (3, 11):
    raise SystemExit("Commons requires Python 3.11 or newer")
PY

if [[ "$scope" == "project" && -z "$project_dir" ]]; then
  project_dir="$PWD"
fi

mkdir -p "$commons_home"
commons_home="$(cd "$commons_home" && pwd -P)"
venv_dir="$commons_home/venv"

if [[ ! -x "$venv_dir/bin/python" ]]; then
  "$python_bin" -m venv "$venv_dir"
fi

(
  cd "$commons_home"
  "$venv_dir/bin/python" -I -m pip install --disable-pip-version-check --upgrade "$source_ref"
)

install_args=(install-skill --target "$target" --scope "$scope")
if [[ -n "$project_dir" ]]; then
  install_args+=(--project-dir "$project_dir")
fi

(
  cd "$commons_home"
  COMMONS_HOME="$commons_home" "$venv_dir/bin/python" -I -m commons.cli "${install_args[@]}"
)

cat <<EOF

Commons is installed.

CLI:   $commons_home/bin/commons
State: $commons_home
Skill: target=$target scope=$scope

Add the CLI to this shell:
  export PATH="$commons_home/bin:\$PATH"

Then verify it:
  commons doctor --json

Installing the Skill does not enroll any workspace. The Agent will ask before
joining a private Relay, using local-only mode, or disabling Commons.
EOF
