# Repository Guidelines

## Project Structure & Module Organization
`cwmscli/` contains the installed CLI package. Root command entry points live in `cwmscli/__main__.py`, shared helpers are under `cwmscli/utils/`, and feature areas such as `load/`, `commands/`, and `usgs/` are split by workflow. Tests are mainly in `tests/` for CLI-level behavior, with additional feature-specific tests under modules such as `cwmscli/commands/csv2cwms/tests/`. Sphinx docs live in `docs/`, and helper scripts such as smoke checks live in `scripts/`.

## Build, Test, and Development Commands
Use Poetry for the local environment:

- `poetry install`: install runtime and dev dependencies.
- `poetry check`: validate `pyproject.toml`.
- `poetry run pytest`: run the test suite.
- `poetry run pre-commit run --all-files`: run formatting hooks before a PR.
- `python -m pip install -e .`: install the CLI in editable mode for manual `cwms-cli` testing.
- `make -C docs html` or `.\docs\make.bat html`: build Sphinx docs.

## Coding Style & Naming Conventions
Python 3.9+ is the target. Formatting is enforced with `black`; imports are normalized with `isort` using the Black profile; YAML is formatted with `yamlfix`. The repository uses UTF-8 and LF line endings by default via `.editorconfig` (`.bat` and `.cmd` stay CRLF). Follow existing naming: modules and packages in `snake_case`, tests named `test_*.py`, and Click-facing command code grouped by command family.

## Testing Guidelines
`pytest` is the active test framework. CLI regression coverage uses Click's `CliRunner`, especially in `tests/cli/` and `tests/commands/`. Add tests alongside the affected command or module, keep names descriptive (`test_update_command.py`, `test_blob_upload.py`), and cover both user-visible output and functional behavior. Run `poetry run pytest` before submitting changes.

## Commit & Pull Request Guidelines
Recent history favors short imperative subjects tied to an issue or PR, for example `Enhance logging configuration with -q option and regression test (#162)`. Keep commits focused and reference the tracking issue when possible. PRs should describe the behavior change, note test coverage, and link the related issue. 

## Documentation Notes
When adding a standalone CLI docs page under `docs/cli/` for a specific subcommand, add it to `docs/index.rst` and also add a direct `:doc:` reference from `docs/cli.rst` or the nearest related command page so it can be discovered from the main CLI reference. Keep examples aligned with the actual Click help and command behavior.
