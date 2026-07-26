#!/usr/bin/env bash
set -euo pipefail

agent="${1:-unknown-agent}"
seconds="${2:-45}"
mkdir -p .demo_state
log=".demo_state/deploy.log"

printf '%s deploy-start agent=%s env=commons-demo/staging\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
for i in $(seq 1 "$seconds"); do
  printf '%s deploy-tick agent=%s second=%s/%s\n' "$(date -u +%FT%TZ)" "$agent" "$i" "$seconds" >> "$log"
  sleep 1
done
printf '%s deploy-finish agent=%s env=commons-demo/staging\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
