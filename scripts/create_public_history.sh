#!/usr/bin/env bash
set -euo pipefail

release_ref="v0.3.0"
head_ref="HEAD"
output=""

usage() {
  cat <<'EOF'
Create a clean two-commit Commons repository without copying private Git history.

Usage:
  ./scripts/create_public_history.sh --output <new-directory> [options]

Options:
  --release-ref <ref>  Public root source tree (default: v0.3.0)
  --head-ref <ref>     Current public development tree (default: HEAD)
  --output <path>      New directory; it must not already exist
  -h, --help

The script requires a clean source worktree and configured Git author identity.
It creates no remote and never pushes or changes the source repository.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release-ref)
      release_ref="${2:?--release-ref requires a value}"
      shift 2
      ;;
    --head-ref)
      head_ref="${2:?--head-ref requires a value}"
      shift 2
      ;;
    --output)
      output="${2:?--output requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$output" ]]; then
  echo "--output is required" >&2
  exit 2
fi

source_root="$(git rev-parse --show-toplevel)"
if [[ -n "$(git -C "$source_root" status --porcelain)" ]]; then
  echo "Source worktree must be clean before creating public history" >&2
  exit 1
fi

git -C "$source_root" rev-parse --verify "${release_ref}^{commit}" >/dev/null
git -C "$source_root" rev-parse --verify "${head_ref}^{commit}" >/dev/null
git -C "$source_root" config user.name >/dev/null
git -C "$source_root" config user.email >/dev/null

output_parent="$(cd "$(dirname "$output")" && pwd -P)"
output="$output_parent/$(basename "$output")"
if [[ -e "$output" ]]; then
  echo "Output path already exists: $output" >&2
  exit 1
fi
case "$output/" in
  "$source_root"/*)
    echo "Output must be outside the source repository: $source_root" >&2
    exit 1
    ;;
esac

mkdir -p "$output"
git -C "$source_root" archive --format=tar "$release_ref" | tar -xf - -C "$output"

git -C "$output" init -b main >/dev/null
git -C "$output" config user.name "$(git -C "$source_root" config user.name)"
git -C "$output" config user.email "$(git -C "$source_root" config user.email)"
git -C "$output" config commit.gpgSign false
git -C "$output" config tag.gpgSign false
git -C "$output" add -A
git -C "$output" commit -m "release: Commons ${release_ref#v}" >/dev/null
git -C "$output" tag -a "$release_ref" -m "Commons ${release_ref#v}"

source_release_tree="$(git -C "$source_root" rev-parse "${release_ref}^{tree}")"
public_release_tree="$(git -C "$output" rev-parse "${release_ref}^{tree}")"
if [[ "$source_release_tree" != "$public_release_tree" ]]; then
  echo "Public release tree does not match source release tree" >&2
  exit 1
fi

git -C "$output" rm -r -q .
git -C "$source_root" archive --format=tar "$head_ref" | tar -xf - -C "$output"
git -C "$output" add -A
if git -C "$output" diff --cached --quiet; then
  echo "Head tree is identical to release tree; refusing an empty second commit" >&2
  exit 1
fi
git -C "$output" commit -m "chore: prepare Commons public development tree" >/dev/null

source_head_tree="$(git -C "$source_root" rev-parse "${head_ref}^{tree}")"
public_head_tree="$(git -C "$output" rev-parse "HEAD^{tree}")"
if [[ "$source_head_tree" != "$public_head_tree" ]]; then
  echo "Public HEAD tree does not match source HEAD tree" >&2
  exit 1
fi

commit_count="$(git -C "$output" rev-list --count --all)"
if [[ "$commit_count" != "2" ]]; then
  echo "Expected exactly two public commits, found $commit_count" >&2
  exit 1
fi
if [[ -n "$(git -C "$output" remote)" ]]; then
  echo "Generated public repository unexpectedly has a remote" >&2
  exit 1
fi

python3 "$output/scripts/check_public_tree.py" --root "$output"

cat <<EOF
Clean public repository candidate created.

Path:                 $output
Release ref:          $release_ref
Release tree:         $public_release_tree
Development ref:      $head_ref
Development tree:     $public_head_tree
Reachable commits:    $commit_count
Configured remotes:   none

Review commit authors, run the complete acceptance suite in this directory,
and follow docs/maintainers/public-repository-cutover.md. This script did not
push or modify the source repository.
EOF
