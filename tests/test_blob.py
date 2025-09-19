from click.testing import CliRunner

from cwmscli.__main__ import cli


def test_blob_list_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["blob", "list", "--help"])
    assert result.exit_code == 0
    assert "List blobs" in result.output
