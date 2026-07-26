# Release Checklist

Use this checklist for PyPI releases and a later public repository launch.
Public-repository, anonymous-clone, and campaign gates apply only when the
repository visibility changes; they do not block a PyPI package release from a
private repository. Record evidence next to each completed gate.

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
- [ ] `make demo` passes all deterministic scenarios.
- [ ] Python sdist and wheel build without warnings.
- [ ] `python -m twine check dist/*` passes.
- [ ] Wheel contains the packaged Commons Skill.
- [ ] Wheel and sdist contain both `LICENSE` and `NOTICE`.
- [ ] The PyPI README is self-contained and does not depend on private repository links.
- [ ] Relay and Console container targets build.
- [ ] Fresh Compose stack passes health, unauthenticated denial, Team-token login, Console overview, and Relay API checks.
- [ ] Real Codex and Claude Code runtime smoke is either passed or explicitly marked `NOT RUN` with reason.

## Security and Privacy

- [ ] No secrets, tokens, credentials, private prompts, raw transcripts, customer data, or browser cookies are present.
- [ ] No personal absolute paths, private hostnames, IP addresses, projects, Agents, or messages are present.
- [ ] Console screenshots and videos use only fixture data.
- [ ] Relay token files and examples use `0600` guidance.
- [ ] Scope-first `remote`, `local`, and `disabled` behavior is documented.
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
- [ ] Wheel, sdist, and Console artifacts have verifiable GitHub build-provenance attestations.

## Documentation and Developer Experience for a Public Repository Launch

- [ ] Anonymous clone works from a clean machine or container.
- [ ] `./scripts/install.sh --source .` installs Codex and Claude Skills in an isolated HOME.
- [ ] README local links and images render on GitHub.
- [ ] Five-minute path succeeds without maintainer assistance.
- [ ] Docker quick start binds to localhost by default.
- [ ] HTTPS requirements for cross-machine deployment are visible.
- [ ] Implementation status and roadmap distinguish shipped and deferred behavior.
- [ ] At least two reviewers can explain what Commons is and what it is not.

## GitHub Repository Settings for a Public Repository Launch

- [ ] Repository description is set.
- [ ] Topics include Agent coordination, Codex, Claude Code, self-hosting, and distributed systems.
- [ ] Wiki is disabled so repository docs remain canonical.
- [ ] Discussions are enabled with `Ideas`, `Q&A`, and `Show and tell` categories.
- [ ] Private vulnerability reporting is enabled before the repository becomes public.
- [ ] Branch protection requires CI and review on `main`.
- [ ] Social preview uses `docs/assets/commons-social-preview.png`.
- [ ] The homepage does not point to the private T54 Labs Console.
- [ ] Issue forms and pull-request template render correctly.

## PyPI Publication

- [ ] `agent-commons` is still unregistered immediately before first publication.
- [ ] The PyPI account owner and token scope are verified before upload.
- [ ] Local token configuration is mode `0600` and never appears in arguments, logs, commits, or GitHub secrets.
- [ ] Wheel and sdist are built from the exact tagged commit and pass `twine check`.
- [ ] `pipx install agent-commons==<version>` succeeds from a clean environment after publication.
- [ ] Configure OIDC Trusted Publishing after the bootstrap release, then retire the account-wide upload token.

## Campaign Assets for a Public Repository Launch

- [ ] 1280x640 social preview is rendered from the release candidate.
- [ ] README screenshot matches the release candidate and contains fixture data only.
- [ ] 30-second demo is captured.
- [ ] 90-second demo is captured.
- [ ] Technical walkthrough commit is named in the description.
- [ ] T54 Labs essay, Hacker News comment, X thread, and LinkedIn copy are reviewed.
- [ ] Launch-day responder and escalation owner are assigned.

## PyPI Publication Order While the Repository Is Private

1. Complete the applicable technical, privacy, licensing, and packaging gates.
2. Freeze the target commit on `main`; align version, changelog, and annotated tag.
3. Push the tag and wait for the release workflow and GitHub Release.
4. Rebuild the Python distributions from the exact tag and run `twine check`.
5. Confirm the name is still available, secure the local token file, and upload once.
6. Verify the PyPI project, hashes, metadata, and a clean pinned `pipx` installation.

## Later Public Repository Launch Order

1. Complete every public-repository and campaign gate above.
2. Make the repository public.
3. Verify anonymous clone, README assets, issues, Discussions, and security reporting.
4. Publish the T54 Labs essay and channel posts.
5. Monitor issues and corrections for at least four hours.

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
