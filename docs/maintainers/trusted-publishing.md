# PyPI Trusted Publishing

Commons publishes `agent-commons` from GitHub Actions with PyPI Trusted
Publishing. The release workflow must not use a long-lived PyPI API token.

The bootstrap release `0.3.0` was uploaded locally and established the PyPI
project. Configure the existing project before the next versioned tag.

## Fixed Publisher Identity

The trusted publisher configuration must use these exact values:

| Field | Value |
| --- | --- |
| PyPI project | `agent-commons` |
| GitHub owner | `t54-labs` |
| GitHub repository | `agent-commons` |
| Workflow filename | `release.yml` |
| GitHub environment | `pypi` |

The identity is bound to the GitHub owner, repository name, workflow filename,
and optional environment. Configure it against the public
`t54-labs/agent-commons` repository. The separate private `t54-labs/commons`
repository is not an authorized publisher.

## 1. Create the GitHub Environment

In the public repository settings, create an environment named `pypi`.

Require manual approval from a small maintainer set. Do not add
`PYPI_API_TOKEN`, a password, or any other PyPI credential as an environment or
repository secret. The release job receives only `id-token: write` permission
and exchanges the GitHub OIDC identity for a short-lived PyPI token.

## 2. Add the Existing-Project Publisher on PyPI

As an owner of `agent-commons`, open the project's Publishing settings and add
a GitHub Actions Trusted Publisher using the fixed identity above.

Confirm every field before submitting. A typo can authorize the wrong workflow
or leave the real workflow unable to publish.

## 3. Verify the Workflow Contract

`.github/workflows/release.yml` must preserve these properties:

- only a pushed `v*` tag starts a release
- Python and product gates complete before artifacts are built
- the wheel and sdist are built exactly once
- `twine check` and `scripts/check_release_artifacts.py` validate them
- GitHub Release and PyPI jobs download the same stored artifacts
- only the PyPI job has the `pypi` environment and `id-token: write`
- `pypa/gh-action-pypi-publish` is pinned to an immutable commit SHA
- no password or API-token input is present

The publish action also creates PyPI-hosted digital attestations for uploaded
distributions. Public GitHub Release assets receive GitHub build-provenance
attestations and a `SHA256SUMS` manifest.

## 4. First OIDC Release

Use the normal release checklist for the next patch version. Update every
pinned onboarding example to that version, merge the release commit, create the
annotated tag, and push only after the candidate passes all gates.

The expected order is:

1. Python and product gates pass.
2. One build job creates and validates the distributions.
3. The GitHub Release is created from the stored release bundle.
4. A maintainer approves the `pypi` environment.
5. PyPI accepts the same wheel and sdist through OIDC.
6. A clean `pipx install agent-commons==<version>` succeeds.
7. PyPI file hashes match the GitHub Release `SHA256SUMS` entries.

Do not use the legacy local token to rescue a failed OIDC run. Diagnose the
publisher identity, environment, permissions, tag, or artifact instead.

## 5. Retire the Bootstrap Token

After the first OIDC publication succeeds:

1. verify the PyPI release and provenance
2. revoke the bootstrap API token in the PyPI account
3. remove its local file from every machine where it was stored
4. verify no `PYPI_API_TOKEN` or `.pypirc` credential exists in GitHub settings
5. record the OIDC workflow run and token revocation in the private maintainer
   release record without copying the token value

PyPI release files are immutable. A broken release is corrected with a new
version; it is never replaced under the same version number.

## References

- [Adding a Trusted Publisher to an existing PyPI project](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [Publishing package distributions with GitHub Actions](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
