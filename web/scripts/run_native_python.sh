#!/bin/sh
set -eu

if [ "$(uname -s)" = "Darwin" ] && [ "$(sysctl -in sysctl.proc_translated 2>/dev/null || true)" = "1" ]; then
  exec /usr/bin/arch -arm64 /usr/bin/env python3 "$@"
fi

exec python3 "$@"
