#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="$ROOT/public/commons-bed.m4a"
RAW_WAV="$(mktemp "${TMPDIR:-/tmp}/commons-bed.XXXXXX")"
trap 'rm -f "$RAW_WAV"' EXIT

node "$ROOT/scripts/generate-audio.mjs" "$RAW_WAV"

ffmpeg -hide_banner -loglevel error -y -i "$RAW_WAV" \
  -af "highpass=f=35,lowpass=f=16000,loudnorm=I=-22:LRA=7:TP=-3" \
  -ar 48000 -c:a aac -b:a 192k "$OUTPUT"

printf 'Generated %s\n' "$OUTPUT"
