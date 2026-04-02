# Contributing to CWMS-CLI

Welcome to the CWMS-CLI contribution guidelines and quick tips. We accept all forms of contributions that follow the below guidelines!

## Getting Started

To get started developing on `cwms-cli` you must first either Fork or Pull down this repo. If you are not one of the [Core Developers](/CONTRIBUTORS.md) then you must Fork the repository and submit your PR from a fork. 

Once you have the repository on your system you can proceed:

1. `poetry install` - Installs required packages setup in [pyproject.toml](/pyproject.toml)
   1. To validate poetry/`pyproject.toml` you can run: `poetry check`
2. `poetry run pre-commit install` - Sets up black and other configurations using [.pre-commit-config.yaml](/.pre-commit-config.yaml) in `.git/hooks`
   1. You can test all files with `poetry run pre-commit run --all-files`
3. `python -m pip install -e .` - This adds cwms-cli and it's commands to your local path allowing you to live develop cwms-cli as a package and test the CLI functions on your system.
4. Run `cwms-cli` to confirm everything installed!

## Running Tests

To run tests you can run: `poetry run pytest`

## Releases

Releases are managed with `release-please`. Do not create releases or tags manually in the GitHub UI.

The release flow is:

1. Merge changes to `main`.
2. GitHub Actions updates or opens a release PR with the proposed version bump and changelog.
3. Review and merge that release PR when the release is ready.
4. The release workflow creates the git tag and GitHub release, publishes to PyPI, and uploads the built artifacts.

Contributor expectations:

- Prefer Conventional Commit style subjects in squash commits or PR titles when practical, for example `fix: handle location regex filtering` or `feat: add blob upload glob support`.
- Keep user-visible changes described clearly in PR titles and merge commits because release notes are assembled from merged work.
- Do not bump `pyproject.toml` manually for normal releases.
- Do not draft a release in the GitHub UI before the release workflow runs.

Maintainer note:

- Repository Settings > Actions > General should allow GitHub Actions to create pull requests, otherwise `release-please` will not be able to open the release PR.

### Conventional Commit Guidance

`release-please` decides the next release version from merged commit messages.

- `fix: ...` creates a patch release.
- `feat: ...` creates a minor release.
- `feat!: ...` creates a major release.
- `BREAKING CHANGE: ...` in the commit body or footer also creates a major release.

Examples:

- `fix: handle duplicate release asset upload`
- `feat: add location ids-bygroup loader`
- `feat!: rename blob upload flags`

If you use squash merge, the PR title usually becomes the final commit subject on `main`, so PR titles should follow this format for user-visible Python changes.

## Helpful Tips

Confirm your packages installed in your environment with:
`poetry show --tree`

## Documentation Ownership

Contributor expectation for `csv2cwms`:

- When practical, user-facing config and parsing errors should link to the
  relevant RTD page so users have a direct path to the correct documentation.
- If you add, rename, or remove config keys, update both the RTD [docs](docs/cli/csv2cwms_complete_config.rst) and the
  [related error guidance](cwmscli/commands/csv2cwms/doclinks.py).

## Formatting

Formatting of code is done via black. You must ensure you have walked through the getting start to setup the `pre-commit` steps for black to match this repositories style practices.  

## Code Review

Create an [issue](https://github.com/hydrologicengineeringcenter/cwms-cli/issues) using one of the templates. Then from that issue on the sidebar select "create branch from issue". This ensures branches are linked to issues and issues are properly closed when resolved. Leaving no orphaned issues.  

## Run GitHub Actions locally

You can rehearse the main GitHub Actions workflows locally with
[`act`](https://github.com/nektos/act) before pushing a branch.


This is **NOT** required and is more of a convenience to test locally before waiting for the actions to run it the first time/subsequent times. 

### Prerequisites:

- `act`
- Docker

### Repo-local setup is already included:

- `.actrc` configures the default `ubuntu-latest` runner image
- `.github/act/pull_request.json` provides a local pull request event payload
- `scripts/run-local-actions.sh` wraps the common workflows

### Examples:

```sh
scripts/run-local-actions.sh cli-tests
scripts/run-local-actions.sh code-check
scripts/run-local-actions.sh docs
scripts/run-local-actions.sh all
```

### Notes:

- When you run `run-local-actions.sh` it will prompt if you would like to install `act`. It assumes you have docker installed already.
- Deployment-oriented workflows such as PyPI publish are not included in the wrapper because they rely on GitHub-hosted credentials and release context.
- You can pass through extra `act` arguments. Example: `scripts/run-local-actions.sh docs -j html`

