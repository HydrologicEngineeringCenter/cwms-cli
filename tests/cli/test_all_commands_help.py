import pytest
from click.testing import CliRunner

from cwmscli.__main__ import cli
from cwmscli.utils.click_help import DOCS_BASE_URL
from cwmscli.utils.version import get_cwms_cli_version

## Expectations
# - The help commands should run without requiring an import
# - Help text should include "Usage: <command> <subcommand> --help"
# - Every command and subcommand should be tested for help text to ensure help renders as expected and no early import errors occur


def iter_commands(cmd, path=()):
    """
    Recursively walk all commands under a Click Group.

    Yields (path_tuple, command_obj), where path_tuple is like:
        ("usgs", "ratings", "etc")
    """
    commands = getattr(cmd, "commands", {})
    for name, sub in commands.items():
        new_path = path + (name,)
        yield new_path, sub
        # If the subcommand is itself a Group, recurse
        if hasattr(sub, "commands"):
            yield from iter_commands(sub, new_path)


@pytest.fixture
def runner():
    return CliRunner()


def test_root_help(runner):
    """Top-level CLI should have working help."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert f"Version: {get_cwms_cli_version()}" in result.output
    assert f"Docs: {DOCS_BASE_URL}/cli.html" in result.output


def test_root_version_flag(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert f"cwms-cli version {get_cwms_cli_version()}" in result.output


@pytest.mark.parametrize("path,command", list(iter_commands(cli)))
def test_every_command_has_help(runner, path, command):
    """
    Run through every command and subcommand, ensuring that the help page renders.
    This ensures that no early import errors occur in any command.
    """
    args = list(path) + ["--help"]
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, f"Failed on: {' '.join(args)}"
    assert "Usage:" in result.output
    assert f"Version: {get_cwms_cli_version()}" in result.output
    if len(path) == 1:
        page_map = {
            "blob": f"{DOCS_BASE_URL}/cli/blob.html",
            "update": f"{DOCS_BASE_URL}/cli/update.html",
        }
        expected_docs = page_map.get(
            path[0], f"{DOCS_BASE_URL}/cli.html#cwms-cli-{path[0]}"
        )
        assert f"Docs: {expected_docs}" in result.output
    else:
        assert "Docs:" not in result.output
