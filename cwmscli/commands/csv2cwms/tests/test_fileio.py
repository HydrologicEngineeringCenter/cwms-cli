import os
import tempfile

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


def test_load_csv_malformed_row():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as malformed:
        malformed.write("Time,Value\n2025-01-01 00:00\n2025-01-01 00:15,42,Extra")
        malformed_path = malformed.name

    try:
        result = load_csv(malformed_path)
        assert len(result) == 3
        assert result[1] == ["2025-01-01 00:00"]
        assert result[2] == ["2025-01-01 00:15", "42", "Extra"]
    finally:
        os.remove(malformed_path)


def test_read_config_valid():
    path = os.path.join(os.path.dirname(__file__), "data", "sample_config.json")
    config = read_config(path)
    assert isinstance(config, dict)
    assert "input_files" in config
    assert "BROK" in config["input_files"]


def test_read_config_invalid_json():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as bad_json:
        bad_json.write("{invalid_json: true,}")
        bad_json_path = bad_json.name

    try:
        with pytest.raises(Exception):
            read_config(bad_json_path)
    finally:
        os.remove(bad_json_path)
