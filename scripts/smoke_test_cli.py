# Used to ensure cli will run under Python 3.9

from click.testing import CliRunner

from cwmscli.cli import cli

runner = CliRunner()
result = runner.invoke(cli, ["--help"])
assert result.exit_code == 0, "CLI failed to run under Python 3.9"
print("CLI loads and runs under Python 3.9")
