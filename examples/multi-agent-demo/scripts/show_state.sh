#!/usr/bin/env bash
set -euo pipefail

mode="${1:-once}"
interval="${2:-2}"

render_once() {
  printf '\033c'
  printf 'Commons multi-agent demo state\n'
  printf 'Updated: %s\n\n' "$(date -u +%FT%TZ)"
  ./scripts/commons.sh watch --once
  printf '\n--- Active leases ---\n'
  ./scripts/commons.sh lease list --active --json
  printf '\n--- Demo logs ---\n'
  for log in .demo_state/*.log; do
    printf '\n[%s]\n' "$log"
    tail -n 8 "$log" || true
  done
}

if [[ "$mode" == "watch" ]]; then
  while true; do
    render_once
    sleep "$interval"
  done
else
  render_once
fi
