import importlib.metadata
import os

from cwmscli.utils.update import get_update_environment


class _Distribution:
    def __init__(self, location):
        self.location = location

    def locate_file(self, path):
        return self.location / path


def test_get_update_environment_reports_virtual_environment(monkeypatch, tmp_path):
    environment_prefix = tmp_path / "venv"
    package_location = environment_prefix / "site-packages"
    python_executable = environment_prefix / "bin" / "python"

    monkeypatch.setattr("cwmscli.utils.update.sys.executable", str(python_executable))
    monkeypatch.setattr("cwmscli.utils.update.sys.prefix", str(environment_prefix))
    monkeypatch.setattr("cwmscli.utils.update.sys.base_prefix", str(tmp_path / "base"))
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.setattr(
        "cwmscli.utils.update.importlib.metadata.distribution",
        lambda name: _Distribution(package_location),
    )

    details = get_update_environment()

    assert details.python_executable == os.path.abspath(python_executable)
    assert details.environment_prefix == os.path.abspath(environment_prefix)
    assert details.environment_type == "virtual environment"
    assert details.package_location == str(package_location.resolve())


def test_get_update_environment_reports_conda_environment(monkeypatch, tmp_path):
    environment_prefix = tmp_path / "conda-env"

    monkeypatch.setattr("cwmscli.utils.update.sys.prefix", str(environment_prefix))
    monkeypatch.setattr("cwmscli.utils.update.sys.base_prefix", str(tmp_path / "base"))
    monkeypatch.setenv("CONDA_PREFIX", str(environment_prefix))
    monkeypatch.setattr(
        "cwmscli.utils.update.importlib.metadata.distribution",
        lambda name: _Distribution(environment_prefix / "site-packages"),
    )

    details = get_update_environment()

    assert details.environment_type == "Conda environment"


def test_get_update_environment_falls_back_for_source_checkout(monkeypatch):
    def missing_distribution(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(
        "cwmscli.utils.update.importlib.metadata.distribution", missing_distribution
    )

    details = get_update_environment()

    assert details.package_location.endswith("cwms-cli")
