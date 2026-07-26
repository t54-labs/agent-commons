#!/usr/bin/env bash
set -euo pipefail

rm -rf .demo_state
mkdir -p .demo_state
touch .demo_state/deploy.log .demo_state/migration.log .demo_state/smoke.log .demo_state/read.log .demo_state/git.log
printf 'not-yet-migrated\n' > .demo_state/db_version.txt

printf 'Demo state reset at %s\n' "$(date -u +%FT%TZ)"
printf 'The isolated demo Commons home was reset with the simulated side-effect logs.\n'
