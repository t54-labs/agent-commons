#!/usr/bin/env bash
set -euo pipefail

agent="${1:-unknown-agent}"
seconds="${2:-35}"
mkdir -p .demo_state
log=".demo_state/migration.log"

printf '%s migration-start agent=%s file=migrations/001_add_audit_log.sql\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
for i in $(seq 1 "$seconds"); do
  printf '%s migration-tick agent=%s second=%s/%s\n' "$(date -u +%FT%TZ)" "$agent" "$i" "$seconds" >> "$log"
  sleep 1
done
printf '001_add_audit_log.sql applied_by=%s applied_at=%s\n' "$agent" "$(date -u +%FT%TZ)" > .demo_state/db_version.txt
printf '%s migration-finish agent=%s version=001_add_audit_log.sql\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
