# Used to ensure the CLI runs on the minimum supported Python version.

from click.testing import CliRunner

from cwmscli.__main__ import cli

runner = CliRunner()
result = runner.invoke(cli, ["--help"])
assert result.exit_code == 0, "CLI failed to run under Python 3.10"
print("CLI loads and runs under Python 3.10")
