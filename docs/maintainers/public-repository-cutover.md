# Public Repository Cutover

This runbook keeps the private `t54-labs/commons` repository unchanged and
publishes a clean, independent history to the public
`t54-labs/agent-commons` repository.

The public repository begins with exactly two commits:

1. the exact source tree of `v0.3.0`, tagged again as `v0.3.0`
2. the current reviewed development tree from the private source `main`

The public commit IDs intentionally differ from the private commit IDs. Their
tree IDs must match, proving that the released and current source trees were
copied byte-for-byte without exposing private history.

## Source-of-Truth Boundary

Before publication:

- `t54-labs/commons` is the private source and historical record.
- `t54-labs/agent-commons` must be empty and receives no private Git objects.

After publication:

- `t54-labs/agent-commons` is the canonical open-source contribution and
  release repository.
- `t54-labs/commons` remains private and preserves its existing issues, pull
  requests, releases, and audit history.
- the private repository must not independently publish packages or release
  tags after the handoff
- ongoing open-source changes should be developed in or deliberately ported to
  the public repository so the two code lines do not silently diverge

No repository rename or GitHub redirect is involved. Existing internal clones
of the private repository keep their current remote, but they are not public
release sources after the handoff.

## Non-Negotiable History Boundary

Do not push, copy, bundle, mirror, or import the private `.git` directory,
refs, reflogs, pull-request refs, GitHub import data, or old commit objects.

Do not use `git filter-repo` as the primary publication strategy. A new
two-commit repository has a smaller and more reviewable disclosure surface.

## 1. Freeze the Publication Trees

Pause merges and pushes to the private source while preparing the public
candidate. Verify both repositories explicitly:

```bash
git -C /path/to/private-commons status --short
git ls-remote git@github.com:t54-labs/agent-commons.git
```

The private source worktree must be clean. The public `git ls-remote` output
must be empty before the first push.

Confirm that package metadata, badges, contribution links, issue links, release
links, and Trusted Publisher documentation all name
`t54-labs/agent-commons`. References to `t54-labs/commons` are allowed only when
they explicitly identify the private historical source.

## 2. Preserve the 0.3.0 Release Assets

Download the existing `v0.3.0` GitHub Release assets from the private source
repository into a directory outside both Git worktrees:

```bash
gh release download v0.3.0 \
  --repo t54-labs/commons \
  --dir /tmp/commons-v0.3.0-release
```

Verify every file against the included `SHA256SUMS`. Do not rebuild 0.3.0 for
the public repository; reuse the artifacts already published and verified
against PyPI.

## 3. Generate the Clean Public Candidate

From the clean private source checkout:

```bash
./scripts/create_public_history.sh \
  --release-ref v0.3.0 \
  --head-ref HEAD \
  --output /tmp/agent-commons-public
```

The script:

- exports trees with `git archive`
- creates a new repository with no remote
- creates one release commit and one development commit
- creates a new annotated `v0.3.0` tag on the release commit
- compares private-source and candidate tree IDs
- requires exactly two reachable commits
- runs the tracked-tree publication scanner
- does not push or modify the private source repository

The generated commits and tag are unsigned so the script remains
non-interactive. If signed provenance is required, recreate them with the
intended verified maintainer identity before adding a remote, then repeat every
tree and history check.

## 4. Audit the Candidate

Run from `/tmp/agent-commons-public`:

```bash
git log --oneline --decorate --all
git rev-list --count --all
git remote -v
git status --short
make test-python
make docs-check
make public-check
make release-source-check
make demo
npm --prefix web ci
npm --prefix web run build
npm --prefix web run test:e2e
```

Required results:

- exactly two reachable commits
- no configured remote
- a clean worktree
- release and development tree IDs match the private source trees
- all Python, documentation, public-tree, deterministic, Console build, and
  Playwright gates pass
- no private commit object is reachable
- no secrets, credentials, private addresses, personal paths, or internal
  runtime state appear in source or visual assets

Run an independent secret scanner over both the candidate directory and its two
commits. Review PNG, audio, and video metadata and visible content separately;
text scanners cannot prove binary assets are clean.

## 5. Push Only the Clean History

Reconfirm the public repository is still empty.

The reconstructed `v0.3.0` tree contains the original tag-triggered release
workflow. If Actions is enabled while that historical tag is pushed, GitHub
will rebuild artifacts and attempt to create a second 0.3.0 Release. That would
replace the reviewed bootstrap assets with a new build. Disable repository
Actions for the tag-only push, restore Actions immediately, and then push
`main` so the current CI runs normally:

```bash
git remote add origin git@github.com:t54-labs/agent-commons.git
gh api -X PUT repos/t54-labs/agent-commons/actions/permissions \
  -F enabled=false
git push origin refs/tags/v0.3.0
gh api -X PUT repos/t54-labs/agent-commons/actions/permissions \
  -F enabled=true \
  -f allowed_actions=all
git push -u origin main
```

Do not use `--mirror`, `--all`, or any remote URL from the private source
checkout. Verify the restored Actions policy with
`gh api repos/t54-labs/agent-commons/actions/permissions` even if either push
fails.

Recreate the public `v0.3.0` GitHub Release from the preserved verified assets.
The public tag commit ID is new, while its tree ID must match the private release
tree. PyPI installation remains `pipx install agent-commons==0.3.0`.

## 6. Configure the Public Repository

Complete these settings immediately after the first push:

- require pull requests and green CI for `main`
- restrict force pushes and branch deletion
- enable Dependabot alerts and security updates
- enable secret scanning and push protection
- enable private vulnerability reporting
- keep blank public issues disabled
- set the Apache-2.0 license, description, topics, and social preview
- create the protected `pypi` environment with maintainer approval
- add the PyPI Trusted Publisher described in
  [PyPI Trusted Publishing](trusted-publishing.md)

The private `t54-labs/commons` repository must not be configured as a PyPI
Trusted Publisher.

## 7. Verify the Public Surface

Verify from an unauthenticated or fresh environment:

```bash
git clone https://github.com/t54-labs/agent-commons.git
cd agent-commons
git rev-list --count --all
make docs-check
make public-check
```

Also verify:

- README images, badges, and links render
- the `v0.3.0` Release assets and `SHA256SUMS` are downloadable
- no release workflow ran for the reconstructed bootstrap tag
- `main` CI ran after Actions was restored
- the Security tab offers private vulnerability reporting
- issue forms and pull-request templates render
- anonymous source installation and the pinned PyPI installation both work
- the next patch release can use OIDC without a long-lived token

Only after these checks should launch communications direct developers to the
public repository.

## Rollback

If sensitive data or private history appears, restrict access to the public
repository immediately and rotate any exposed credential. Do not assume that
deleting one branch or tag removes already fetched objects.

The private repository remains intact. A failed public candidate can be
discarded and regenerated from the reviewed trees without rewriting the
private history.
