import importlib
import sys
import types

from click.testing import CliRunner

import cwmscli.utils.deps as deps
from cwmscli import usgs as usgs_module
from cwmscli import utils as utils_module
from cwmscli.__main__ import cli
from cwmscli.commands import commands_cwms


def _reload_utils():
    return importlib.reload(utils_module)


def test_api_key_loc_overrides_env_api_key(tmp_path):
    key_file = tmp_path / "cda_api_key.txt"
    key_file.write_text("file-key\n", encoding="utf-8")

    utils = _reload_utils()
    assert utils.get_api_key("env-key", str(key_file)) == "file-key"


def test_api_key_loc_takes_precedence_when_both_are_provided(tmp_path):
    key_file = tmp_path / "cda_api_key.txt"
    key_file.write_text("file-key\n", encoding="utf-8")

    utils = _reload_utils()
    assert utils.get_api_key("cli-key", str(key_file)) == "file-key"


def test_usgs_timeseries_api_key_loc_overrides_env(monkeypatch, tmp_path):
    captured = {}
    fake_module = types.ModuleType("cwmscli.usgs.getusgs_cda")

    def fake_getusgs_cda(**kwargs):
        captured.update(kwargs)

    fake_module.getusgs_cda = fake_getusgs_cda

    key_file = tmp_path / "cda_api_key.txt"
    key_file.write_text("file-key\n", encoding="utf-8")
    utils = _reload_utils()

    monkeypatch.setitem(sys.modules, "cwmscli.usgs.getusgs_cda", fake_module)
    monkeypatch.setattr(deps.importlib, "import_module", lambda name: object())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda name: "999.0.0")
    monkeypatch.setattr(usgs_module, "get_api_key", utils.get_api_key)
    result = CliRunner().invoke(
        cli,
        [
            "usgs",
            "timeseries",
            "-o",
            "spl",
            "-d",
            "1",
            "-a",
            "https://example.test/cda/",
            "--api-key-loc",
            str(key_file),
        ],
        env={"CDA_API_KEY": "env-key"},
    )

    assert result.exit_code == 0, result.output
    assert captured["api_key"] == "file-key"


def test_shefcritimport_api_key_loc_overrides_env(monkeypatch, tmp_path):
    captured = {}
    fake_module = types.ModuleType("cwmscli.commands.shef.import_critfile")

    def fake_import_shef_critfile(**kwargs):
        captured.update(kwargs)

    fake_module.import_shef_critfile = fake_import_shef_critfile

    key_file = tmp_path / "cda_api_key.txt"
    key_file.write_text("file-key\n", encoding="utf-8")
    shef_file = tmp_path / "sample.crit"
    shef_file.write_text("sample\n", encoding="utf-8")
    utils = _reload_utils()

    monkeypatch.setitem(
        sys.modules, "cwmscli.commands.shef.import_critfile", fake_module
    )
    monkeypatch.setattr(deps.importlib, "import_module", lambda name: object())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda name: "999.0.0")
    monkeypatch.setattr(commands_cwms, "get_api_key", utils.get_api_key, raising=False)
    result = CliRunner().invoke(
        cli,
        [
            "shef",
            "import_crit",
            "-f",
            str(shef_file),
            "-o",
            "spl",
            "-a",
            "https://example.test/cda/",
            "--api-key-loc",
            str(key_file),
        ],
        env={"CDA_API_KEY": "env-key"},
    )

    assert result.exit_code == 0, result.output
    assert captured["api_key"] == "file-key"


def test_shefinfile_import_api_key_loc_overrides_env(monkeypatch, tmp_path):
    captured = {}
    fake_module = types.ModuleType("cwmscli.commands.shef.import_infile")

    def fake_import_shef_infile(**kwargs):
        captured.update(kwargs)

    fake_module.import_shef_infile = fake_import_shef_infile

    key_file = tmp_path / "cda_api_key.txt"
    key_file.write_text("file-key\n", encoding="utf-8")
    in_file = tmp_path / "sample.in"
    in_file.write_text("sample\n", encoding="utf-8")
    utils = _reload_utils()

    monkeypatch.setitem(sys.modules, "cwmscli.commands.shef.import_infile", fake_module)
    monkeypatch.setattr(deps.importlib, "import_module", lambda name: object())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda name: "999.0.0")
    monkeypatch.setattr(commands_cwms, "get_api_key", utils.get_api_key, raising=False)
    result = CliRunner().invoke(
        cli,
        [
            "shef",
            "import_infile",
            "-f",
            str(in_file),
            "-g",
            "test-group",
            "-o",
            "spl",
            "-a",
            "https://example.test/cda/",
            "--api-key-loc",
            str(key_file),
        ],
        env={"CDA_API_KEY": "env-key"},
    )

    assert result.exit_code == 0, result.output
    assert captured["api_key"] == "file-key"
