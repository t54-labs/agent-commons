# Release Checklist

Use this checklist for the initial `t54-labs/agent-commons` source publication
and every later PyPI/GitHub release. The private bootstrap release is complete;
future releases originate from the public repository. Record evidence next to
each completed gate.

## Release Identity

- [ ] Release owner is named.
- [ ] Release version and target commit are frozen.
- [ ] `commons.__version__`, tag, changelog, and release title agree.
- [ ] The target commit is on `main` and pushed to origin.
- [ ] No unrelated worktree changes are present.

## Code and Tests

- [ ] `make test-python` passes.
- [ ] `make docs-check` passes.
- [ ] `npm --prefix web run build` passes.
- [ ] `npm --prefix web run test:e2e` passes on desktop and mobile Chromium.
- [ ] `npm --prefix video run check` passes for the Remotion product-video source.
- [ ] `make demo` passes all deterministic scenarios.
- [ ] Python sdist and wheel build without warnings.
- [ ] `python -m twine check dist/*` passes.
- [ ] Wheel contains the packaged Commons Skill.
- [ ] Wheel and sdist contain both `LICENSE` and `NOTICE`.
- [ ] The PyPI README is self-contained and does not depend on private repository links.
- [ ] Relay and Console container targets build.
- [ ] Fresh Compose stack passes health, unauthenticated denial, Team-token login, Console overview, and Relay API checks.
- [ ] Real Codex, Claude Code, and Cline runtime smoke is either passed or explicitly marked `NOT RUN` with reason.
- [ ] A clean 0.4.0 client-to-0.5.0 upgrade refreshes all global Skills and preserves existing Relay state.
- [ ] New Agent registration rejects missing or mismatched human attribution, while existing legacy Agents remain readable.

## Security and Privacy

- [ ] No secrets, tokens, credentials, private prompts, raw transcripts, customer data, or browser cookies are present.
- [ ] No personal absolute paths, private hostnames, IP addresses, projects, Agents, or messages are present.
- [ ] Console screenshots and videos use only fixture data.
- [ ] Every public image and audio file has a documented source or generation path in `docs/assets/README.md`.
- [ ] Relay token files and examples use `0600` guidance.
- [ ] Scope-first `remote`, `local`, and `disabled` behavior is documented.
- [ ] Human-owner prompts do not infer identity from account, Git, email, host, or workspace metadata.
- [ ] Public Relay and untrusted multi-tenant operation remain explicit non-goals.
- [ ] Advisory versus wrapper-enforced lease behavior is explicit.
- [ ] Vulnerability reporting and a confidential Code of Conduct channel are configured.

## Licensing and Supply Chain

- [ ] GitHub identifies the repository license as Apache-2.0.
- [ ] `LICENSE` matches the official Apache 2.0 text.
- [ ] `NOTICE` contains T54 Labs attribution.
- [ ] Python metadata uses the SPDX `Apache-2.0` expression.
- [ ] GitHub Actions are pinned to immutable commit SHAs.
- [ ] Dependency lockfiles are committed.
- [ ] Dependabot configuration is enabled and initial alerts are reviewed.
- [ ] Release artifacts contain no private or generated test state.
- [ ] Wheel, sdist, and Console artifacts have verifiable SHA-256 checksums.
- [ ] Public-repository release artifacts also have verifiable GitHub build-provenance attestations.

## Documentation and Developer Experience for a Public Repository Launch

- [ ] The public candidate was generated with `scripts/create_public_history.sh`, not by copying or rewriting the private `.git` directory.
- [ ] The public `v0.3.0` and development tree IDs match their reviewed private source trees.
- [ ] The public candidate has exactly two reachable commits and no remote before review.
- [ ] Repository Actions are disabled only for the reconstructed `v0.3.0` tag push, restored immediately, and verified before `main` is pushed.
- [ ] No historical release workflow rebuilds or republishes the preserved bootstrap assets.
- [ ] `make public-check` and an independent secret scanner pass on the candidate and both public commits.
- [ ] Anonymous clone works from a clean machine or container.
- [ ] `./scripts/install.sh --source .` installs Codex, Claude Code, and Cline Skills in an isolated HOME.
- [ ] README local links and images render on GitHub.
- [ ] Five-minute path succeeds without maintainer assistance.
- [ ] Docker quick start binds to localhost by default.
- [ ] HTTPS requirements for cross-machine deployment are visible.
- [ ] Implementation status and roadmap distinguish shipped and deferred behavior.
- [ ] At least two reviewers can explain what Commons is and what it is not.

## GitHub Repository Settings for a Public Repository Launch

- [ ] Repository description is set.
- [ ] Topics include Agent coordination, Codex, Claude Code, Cline, self-hosting, and distributed systems.
- [ ] Wiki is disabled so repository docs remain canonical.
- [ ] Discussions are enabled with `Ideas`, `Q&A`, and `Show and tell` categories once moderation ownership is assigned.
- [ ] Private vulnerability reporting is enabled before source is pushed or launch traffic is directed to the repository.
- [ ] Branch protection requires CI and review on `main`.
- [ ] Social preview uses `docs/assets/commons-social-preview.png`.
- [ ] The homepage does not point to the private T54 Labs Console.
- [ ] Issue forms and pull-request template render correctly.

## PyPI Publication

- [ ] The `agent-commons` project owner and release owner are verified.
- [ ] The PyPI Trusted Publisher matches owner `t54-labs`, repository `agent-commons`, workflow `release.yml`, and environment `pypi`.
- [ ] The GitHub `pypi` environment requires maintainer approval.
- [ ] No `PYPI_API_TOKEN`, password, or long-lived PyPI credential exists in GitHub settings or the workflow.
- [ ] Wheel and sdist are built from the exact tagged commit and pass `twine check`.
- [ ] `scripts/check_release_artifacts.py --tag v<version> --dist-dir <dir>` passes.
- [ ] GitHub Release and PyPI consume the same stored wheel and sdist.
- [ ] `pipx install agent-commons==<version>` succeeds from a clean environment after publication.
- [ ] PyPI hashes match the GitHub Release `SHA256SUMS` entries.
- [ ] The bootstrap upload token is revoked after the first successful OIDC publication.

## Campaign Assets for a Public Repository Launch

- [ ] 1280x640 social preview is rendered from the release candidate.
- [ ] README screenshot matches the release candidate and contains fixture data only.
- [ ] 30-second demo is captured.
- [ ] 90-second demo is captured.
- [ ] Technical walkthrough commit is named in the description.
- [ ] T54 Labs essay, Hacker News comment, X thread, and LinkedIn copy are reviewed.
- [ ] Launch-day responder and escalation owner are assigned.

## PyPI Publication Order

1. Complete every technical, privacy, licensing, packaging, and onboarding-pin gate.
2. Freeze the target commit on `main`; align version, changelog, and annotated tag.
3. Push the tag and wait for Python and product release gates.
4. Verify the single build job passes `twine check` and artifact inspection.
5. Verify the GitHub Release and `SHA256SUMS` bundle.
6. Approve the protected `pypi` environment.
7. Verify the OIDC publication, attestations, hashes, metadata, and a clean pinned pipx installation.

For `0.5.0`, upgrade clients and refresh all global Skills before relying on
Cline registration. Verify `commons user show --json`, Cline Skill discovery,
and explicit runtime attribution on each participating machine, then run the
remote acceptance suite. The Relay must never attempt to mutate a client's
local Skill files.

## Initial Public Repository Launch Order

1. Keep the private `t54-labs/commons` repository unchanged and freeze its publication trees.
2. Confirm the public `t54-labs/agent-commons` repository is empty.
3. Generate and audit the clean two-commit public candidate.
4. Disable Actions for the reconstructed `v0.3.0` tag-only push, restore and verify Actions, then push candidate `main` so current CI runs.
5. Recreate the verified `v0.3.0` release assets without rebuilding them.
6. Configure branch protection, secret scanning, push protection, private vulnerability reporting, and the protected `pypi` environment.
7. Configure PyPI Trusted Publishing for `t54-labs/agent-commons`; never authorize the private repository.
8. Verify anonymous clone, README assets, issues, security reporting, release assets, and the complete CI matrix.
9. Publish the T54 Labs essay and channel posts.
10. Monitor issues and corrections for at least four hours.

## Rollback

- [ ] A release can be marked as a prerelease or withdrawn without deleting Git history.
- [ ] Compromised tokens can be rotated independently from source publication.
- [ ] Incorrect screenshots or copy can be replaced with a documented correction.
- [ ] A broken package release is superseded with a new patch version, never silently replaced.
- [ ] Security-sensitive reports are moved to the private advisory process immediately.

## Post-Release

- [ ] Record GitHub Actions run URLs and release asset hashes.
- [ ] Triage every P0/P1 report before promotional follow-up.
- [ ] Convert repeated setup failures into docs, tests, or installer fixes.
- [ ] Thank first Contributors and reviewers with links to accepted work.
- [ ] Publish a two-week retrospective and update the roadmap.
