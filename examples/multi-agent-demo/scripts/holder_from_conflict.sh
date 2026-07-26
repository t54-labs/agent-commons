#!/usr/bin/env bash
set -euo pipefail

resource="${1:?resource is required}"
mode="${2:-write}"

./scripts/commons.sh lease conflicts "$resource" --mode "$mode" --json |
  python3 -c '
import json
import sys

payload = json.load(sys.stdin)
conflicts = payload.get("conflicts") or []
if not conflicts:
    raise SystemExit("no active conflicting holder found")
holder = conflicts[0].get("holder_agent_id")
if not holder:
    raise SystemExit("conflict has no holder_agent_id")
print(holder)
'
