import importlib.metadata
import sys
from unittest.mock import Mock

import click
import pytest
from click.testing import CliRunner

from cwmscli import requirements
from cwmscli.utils import deps


def expected_pip_command(*args):
    return f'"{sys.executable}" -m pip install {" ".join(args)}'


@pytest.mark.parametrize("version", ["2.0.0", "2.1.0", "10.0.0", "2.0.0rc1"])
def test_cwms_rejects_unsupported_versions(monkeypatch, version):
    monkeypatch.setattr(deps.importlib, "import_module", Mock())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda _: version)
    callback = Mock()
    command = click.command()(deps.requires(requirements.cwms)(callback))
    result = CliRunner().invoke(command)
    assert result.exit_code == 1
    assert version in result.output
    assert ">=1.0.7,<2.0.0" in result.output
    assert expected_pip_command("--upgrade", "cwms-cli") in result.output
    assert (
        expected_pip_command("--upgrade", '"cwms-python>=1.0.7,<2.0.0"')
        in result.output
    )
    callback.assert_not_called()


@pytest.mark.parametrize(
    "version", ["1.0.7", "1.0.10", "1.9.0", "1.10.0", "1.0.7.post1"]
)
def test_cwms_accepts_supported_versions(monkeypatch, version):
    monkeypatch.setattr(deps.importlib, "import_module", Mock())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda _: version)
    callback = Mock(return_value="ok")
    assert deps.requires(requirements.cwms)(callback)() == "ok"
    callback.assert_called_once()


@pytest.mark.parametrize("version", ["1.0.6", "1.0.7rc1", "invalid"])
def test_cwms_rejects_old_or_unverifiable_versions(monkeypatch, version):
    monkeypatch.setattr(deps.importlib, "import_module", Mock())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda _: version)
    callback = Mock()
    with pytest.raises(click.ClickException) as exc:
        deps.requires(requirements.cwms)(callback)()
    expected_args = ["--upgrade", '"cwms-python>=1.0.7,<2.0.0"']
    if version == "invalid":
        expected_args.insert(1, "--force-reinstall")
    assert expected_pip_command(*expected_args) in str(exc.value)
    callback.assert_not_called()


def test_minimum_only_requirement_still_allows_newer_versions(monkeypatch):
    monkeypatch.setattr(deps.importlib, "import_module", Mock())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda _: "10.0.0")
    callback = Mock()
    deps.requires({"module": "example", "version": "2.9.0"})(callback)()
    callback.assert_called_once()


def test_missing_module_suggests_supported_range(monkeypatch):
    monkeypatch.setattr(deps.importlib, "import_module", Mock(side_effect=ImportError))
    with pytest.raises(click.ClickException, match="Missing module") as exc:
        deps.requires(requirements.cwms)(Mock())()
    assert expected_pip_command("--upgrade", '"cwms-python>=1.0.7,<2.0.0"') in str(
        exc.value
    )


def test_missing_metadata_blocks_command(monkeypatch):
    monkeypatch.setattr(deps.importlib, "import_module", Mock())
    monkeypatch.setattr(
        deps.importlib.metadata,
        "version",
        Mock(side_effect=importlib.metadata.PackageNotFoundError),
    )
    with pytest.raises(click.ClickException, match="version could not be verified"):
        deps.requires(requirements.cwms)(Mock())()


def test_upper_bound_without_minimum(monkeypatch):
    monkeypatch.setattr(deps.importlib, "import_module", Mock())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda _: "3.0.0")
    with pytest.raises(click.ClickException, match="<3.0.0"):
        deps.requires({"module": "example", "max_version": "3.0.0"})(Mock())()


def test_unversioned_requirement_does_not_need_metadata(monkeypatch):
    monkeypatch.setattr(deps.importlib, "import_module", Mock())
    metadata = Mock(side_effect=AssertionError("should not read metadata"))
    monkeypatch.setattr(deps.importlib.metadata, "version", metadata)
    callback = Mock()
    deps.requires({"module": "example"})(callback)()
    callback.assert_called_once()


def test_real_cli_blocks_newer_cwms_before_command_runs(monkeypatch):
    from cwmscli.__main__ import cli

    monkeypatch.delenv("CDA_API_ROOT", raising=False)
    monkeypatch.setattr(deps.importlib, "import_module", Mock())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda _: "2.0.0")
    result = CliRunner().invoke(
        cli,
        ["users", "roles", "list-all", "--api-root", "https://example.test/cda/"],
    )
    assert result.exit_code == 1, result.output
    assert "cwms-python" in result.output
    assert ">=1.0.7,<2.0.0" in result.output
