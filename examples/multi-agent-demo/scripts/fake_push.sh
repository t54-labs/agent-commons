#!/usr/bin/env bash
set -euo pipefail

agent="${1:-unknown-agent}"
seconds="${2:-20}"
mkdir -p .demo_state
log=".demo_state/git.log"

printf '%s push-start agent=%s branch=commons-demo/main\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
for i in $(seq 1 "$seconds"); do
  printf '%s push-tick agent=%s second=%s/%s\n' "$(date -u +%FT%TZ)" "$agent" "$i" "$seconds" >> "$log"
  sleep 1
done
printf '%s push-finish agent=%s branch=commons-demo/main\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
