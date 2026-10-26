from click.testing import CliRunner

from cwmscli.__main__ import cli


def test_blob_list_rejects_zero_limit():
    result = CliRunner().invoke(
        cli,
        [
            "blob",
            "list",
            "--office",
            "SWT",
            "--api-root",
            "https://example.test/cwms-data/",
            "--limit",
            "0",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--limit'" in result.output


def test_blob_list_rejects_negative_page_size():
    result = CliRunner().invoke(
        cli,
        [
            "blob",
            "list",
            "--office",
            "SWT",
            "--api-root",
            "https://example.test/cwms-data/",
            "--page-size",
            "-1",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--page-size'" in result.output


def test_clob_list_rejects_zero_limit():
    result = CliRunner().invoke(
        cli,
        [
            "clob",
            "list",
            "--office",
            "SWT",
            "--api-root",
            "https://example.test/cwms-data/",
            "--limit",
            "0",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--limit'" in result.output
