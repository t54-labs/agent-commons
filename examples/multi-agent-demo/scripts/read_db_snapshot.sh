#!/usr/bin/env bash
set -euo pipefail

agent="${1:-unknown-agent}"
mkdir -p .demo_state
log=".demo_state/read.log"
version_file=".demo_state/db_version.txt"

printf '%s read-start agent=%s resource=db:commons-demo/staging\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
if [[ -f "$version_file" ]]; then
  printf '%s read-version agent=%s version=%s\n' "$(date -u +%FT%TZ)" "$agent" "$(tr '\n' ' ' < "$version_file")" >> "$log"
else
  printf '%s read-version agent=%s version=not-yet-migrated\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
fi
sleep 3
printf '%s read-finish agent=%s\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
