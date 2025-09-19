import os

import pytest

from ..utils.fileio import load_csv, read_config


def test_load_csv_valid():
    path = os.path.join(os.path.dirname(__file__), "data", "sample_brok.csv")
    result = load_csv(path)
    assert isinstance(result, list)
    assert isinstance(result[0], list)
    assert len(result[0]) > 1  # header row should have multiple columns


def test_load_csv_nonexistent():
    path = os.path.join(os.path.dirname(__file__), "data", "does_not_exist.csv")
    with pytest.raises(FileNotFoundError):
        load_csv(path)


def test_load_csv_malformed_row(tmp_path):
    malformed = tmp_path / "bad.csv"
    malformed.write_text("Time,Value\n2025-01-01 00:00\n2025-01-01 00:15,42,Extra")
    result = load_csv(str(malformed))
    assert len(result) == 3
    assert result[1] == ["2025-01-01 00:00"]
    assert result[2] == ["2025-01-01 00:15", "42", "Extra"]


def test_read_config_valid():
    path = os.path.join(os.path.dirname(__file__), "data", "sample_config.json")
    config = read_config(path)
    assert isinstance(config, dict)
    assert "input_files" in config
    assert "BROK" in config["input_files"]


def test_read_config_invalid_json(tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{invalid_json: true,}")
    with pytest.raises(Exception):
        read_config(str(bad_json))
