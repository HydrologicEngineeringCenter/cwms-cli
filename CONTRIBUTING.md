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

## Helpful Tips

Confirm your packages installed in your environment with:
`poetry show --tree`

## Formatting

Formatting of code is done via black. You must ensure you have walked through the getting start to setup the `pre-commit` steps for black to match this repositories style practices.  

## Code Review

Create an [issue](https://github.com/hydrologicengineeringcenter/cwms-cli/issues) using one of the templates. Then from that issue on the sidebar select "create branch from issue". This ensures branches are linked to issues and issues are properly closed when resolved. Leaving no orphaned issues.  
