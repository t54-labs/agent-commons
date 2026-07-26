#!/usr/bin/env bash
set -euo pipefail

agent="${1:-unknown-agent}"
mkdir -p .demo_state
log=".demo_state/smoke.log"

printf '%s smoke-start agent=%s env=commons-demo/staging\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
python3 -m py_compile src/payment_api.py src/worker.py
printf '%s smoke-check agent=%s py_compile=ok\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
sleep 4
printf '%s smoke-finish agent=%s status=ok\n' "$(date -u +%FT%TZ)" "$agent" >> "$log"
