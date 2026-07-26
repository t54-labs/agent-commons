#!/usr/bin/env bash
set -euo pipefail

role="${1:?role is required}"
runtime="${2:-auto}"
title="${3:-Commons demo role: $role}"
mkdir -p .demo_state

task_json="$(./scripts/commons.sh --json task create "$title")"
task_id="$(printf '%s' "$task_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["task_id"])')"
agent_json="$(./scripts/commons.sh --json agent register --runtime "$runtime" --workspace "$PWD" --name "$role" --task "$task_id")"
agent_id="$(printf '%s' "$agent_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["agent_id"])')"

env_file=".demo_state/${role}.env"
{
  printf 'export ROLE=%q\n' "$role"
  printf 'export TASK_ID=%q\n' "$task_id"
  printf 'export AGENT_ID=%q\n' "$agent_id"
} > "$env_file"

printf 'export ROLE=%q\n' "$role"
printf 'export TASK_ID=%q\n' "$task_id"
printf 'export AGENT_ID=%q\n' "$agent_id"
printf '# registered %s as %s for %s\n' "$role" "$agent_id" "$task_id" >&2
