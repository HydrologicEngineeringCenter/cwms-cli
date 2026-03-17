import importlib
from datetime import datetime

import pytest


def test_load_timeseries_missing_column_aborts(monkeypatch):
    monkeypatch.setenv("CDA_API_KEY", "test-key")
    monkeypatch.setenv("CDA_OFFICE", "SWT")
    monkeypatch.setenv("CDA_HOST", "https://example.test")

    csv2_main = importlib.import_module("cwmscli.commands.csv2cwms.__main__")

    file_data = {
        "header": ["Time", "Headwater", "Tailwater"],
        "data": {
            1742938200: ["03/25/2025 20:30:00", "599.95", "405.54"],
            1742939100: ["03/25/2025 20:45:00", "599.92", "405.53"],
        },
    }
    config = {
        "interval": 900,
        "input_files": {
            "BROK": {
                "timeseries": {
                    "BROK.Bad.Inst.15Minutes.0.Rev-SCADA-cda": {
                        "columns": "Headwater+MissingColumn",
                        "units": "ft",
                        "precision": 2,
                    }
                }
            }
        },
    }

    with pytest.raises(ValueError) as excinfo:
        csv2_main.load_timeseries(file_data, "BROK", config)

    message = str(excinfo.value)
    assert "Configured CSV columns were not found in the input file" in message
    assert "Skipping BROK" in message
    assert "Headwater+MissingColumn" in message
    assert "MissingColumn" in message
    assert "Available CSV columns: Time, Headwater, Tailwater" in message


def test_load_timeseries_rounds_to_nearest_interval(monkeypatch):
    monkeypatch.setenv("CDA_API_KEY", "test-key")
    monkeypatch.setenv("CDA_OFFICE", "SWT")
    monkeypatch.setenv("CDA_HOST", "https://example.test")

    csv2_main = importlib.import_module("cwmscli.commands.csv2cwms.__main__")
    tz = csv2_main.safe_zoneinfo("UTC")

    file_data = {
        "header": ["Time", "Headwater"],
        "data": {
            int(datetime(2025, 3, 25, 12, 7, tzinfo=tz).timestamp()): [
                "2025-03-25 12:07",
                "10.0",
            ],
            int(datetime(2025, 3, 25, 12, 52, tzinfo=tz).timestamp()): [
                "2025-03-25 12:52",
                "20.0",
            ],
        },
        "source_timezone": tz,
    }
    config = {
        "round_to_nearest": True,
        "input_files": {
            "BROK": {
                "timeseries": {
                    "BROK.Elev.Inst.1Hour.0.Rev-SCADA-cda": {
                        "columns": "Headwater",
                        "units": "ft",
                        "precision": 2,
                    }
                }
            }
        },
    }

    result = csv2_main.load_timeseries(file_data, "BROK", config)

    assert result[0]["values"] == [
        [int(datetime(2025, 3, 25, 12, 0, tzinfo=tz).timestamp()) * 1000, 10.0, 3],
        [int(datetime(2025, 3, 25, 13, 0, tzinfo=tz).timestamp()) * 1000, 20.0, 3],
    ]


def test_load_timeseries_uses_raw_timestamps_when_rounding_disabled(monkeypatch):
    monkeypatch.setenv("CDA_API_KEY", "test-key")
    monkeypatch.setenv("CDA_OFFICE", "SWT")
    monkeypatch.setenv("CDA_HOST", "https://example.test")

    csv2_main = importlib.import_module("cwmscli.commands.csv2cwms.__main__")
    tz = csv2_main.safe_zoneinfo("UTC")
    first_epoch = int(datetime(2025, 3, 25, 12, 7, tzinfo=tz).timestamp())
    second_epoch = int(datetime(2025, 3, 25, 12, 24, tzinfo=tz).timestamp())

    file_data = {
        "header": ["Time", "Headwater"],
        "data": {
            first_epoch: ["2025-03-25 12:07", "10.0"],
            second_epoch: ["2025-03-25 12:24", "20.0"],
        },
        "source_timezone": tz,
    }
    config = {
        "interval": second_epoch - first_epoch,
        "input_files": {
            "BROK": {
                "timeseries": {
                    "BROK.Elev.Inst.1Hour.0.Rev-SCADA-cda": {
                        "columns": "Headwater",
                        "units": "ft",
                        "precision": 2,
                    }
                }
            }
        },
    }

    result = csv2_main.load_timeseries(file_data, "BROK", config)

    assert result[0]["values"] == [
        [first_epoch * 1000, 10.0, 3],
        [second_epoch * 1000, 20.0, 3],
    ]


def test_load_timeseries_rounds_to_configured_interval_when_present(monkeypatch):
    monkeypatch.setenv("CDA_API_KEY", "test-key")
    monkeypatch.setenv("CDA_OFFICE", "SWT")
    monkeypatch.setenv("CDA_HOST", "https://example.test")

    csv2_main = importlib.import_module("cwmscli.commands.csv2cwms.__main__")
    tz = csv2_main.safe_zoneinfo("UTC")

    file_data = {
        "header": ["Time", "Headwater"],
        "data": {
            int(datetime(2025, 3, 25, 12, 7, tzinfo=tz).timestamp()): [
                "2025-03-25 12:07",
                "10.0",
            ],
            int(datetime(2025, 3, 25, 12, 24, tzinfo=tz).timestamp()): [
                "2025-03-25 12:24",
                "20.0",
            ],
        },
        "source_timezone": tz,
    }
    config = {
        "interval": 1800,
        "round_to_nearest": True,
        "input_files": {
            "BROK": {
                "timeseries": {
                    "BROK.Elev.Inst.1Hour.0.Rev-SCADA-cda": {
                        "columns": "Headwater",
                        "units": "ft",
                        "precision": 2,
                    }
                }
            }
        },
    }

    result = csv2_main.load_timeseries(file_data, "BROK", config)

    assert result[0]["values"] == [
        [int(datetime(2025, 3, 25, 12, 0, tzinfo=tz).timestamp()) * 1000, 10.0, 3],
        [int(datetime(2025, 3, 25, 12, 30, tzinfo=tz).timestamp()) * 1000, 20.0, 3],
    ]


def test_load_timeseries_uses_last_value_when_multiple_found(monkeypatch):
    monkeypatch.setenv("CDA_API_KEY", "test-key")
    monkeypatch.setenv("CDA_OFFICE", "SWT")
    monkeypatch.setenv("CDA_HOST", "https://example.test")

    csv2_main = importlib.import_module("cwmscli.commands.csv2cwms.__main__")
    tz = csv2_main.safe_zoneinfo("UTC")
    rounded_epoch = int(datetime(2025, 3, 25, 12, 0, tzinfo=tz).timestamp())

    file_data = {
        "header": ["Time", "Headwater"],
        "data": {
            int(datetime(2025, 3, 25, 12, 7, tzinfo=tz).timestamp()): [
                "2025-03-25 12:07",
                "10.0",
            ],
            int(datetime(2025, 3, 25, 12, 24, tzinfo=tz).timestamp()): [
                "2025-03-25 12:24",
                "20.0",
            ],
        },
        "source_timezone": tz,
    }
    config = {
        "round_to_nearest": True,
        "use_if_multiple": "last",
        "input_files": {
            "BROK": {
                "timeseries": {
                    "BROK.Elev.Inst.1Hour.0.Rev-SCADA-cda": {
                        "columns": "Headwater",
                        "units": "ft",
                        "precision": 2,
                    }
                }
            }
        },
    }

    result = csv2_main.load_timeseries(file_data, "BROK", config)

    assert result[0]["values"] == [[rounded_epoch * 1000, 20.0, 3]]


def test_load_timeseries_averages_multiple_values_when_configured(monkeypatch):
    monkeypatch.setenv("CDA_API_KEY", "test-key")
    monkeypatch.setenv("CDA_OFFICE", "SWT")
    monkeypatch.setenv("CDA_HOST", "https://example.test")

    csv2_main = importlib.import_module("cwmscli.commands.csv2cwms.__main__")
    tz = csv2_main.safe_zoneinfo("UTC")
    rounded_epoch = int(datetime(2025, 3, 25, 12, 0, tzinfo=tz).timestamp())

    file_data = {
        "header": ["Time", "Headwater"],
        "data": {
            int(datetime(2025, 3, 25, 12, 7, tzinfo=tz).timestamp()): [
                "2025-03-25 12:07",
                "10.0",
            ],
            int(datetime(2025, 3, 25, 12, 24, tzinfo=tz).timestamp()): [
                "2025-03-25 12:24",
                "20.0",
            ],
        },
        "source_timezone": tz,
    }
    config = {
        "round_to_nearest": True,
        "use_if_multiple": "average",
        "input_files": {
            "BROK": {
                "timeseries": {
                    "BROK.Elev.Inst.1Hour.0.Rev-SCADA-cda": {
                        "columns": "Headwater",
                        "units": "ft",
                        "precision": 2,
                    }
                }
            }
        },
    }

    result = csv2_main.load_timeseries(file_data, "BROK", config)

    assert result[0]["values"] == [[rounded_epoch * 1000, 15.0, 3]]


def test_load_timeseries_errors_on_multiple_values_when_configured(monkeypatch):
    monkeypatch.setenv("CDA_API_KEY", "test-key")
    monkeypatch.setenv("CDA_OFFICE", "SWT")
    monkeypatch.setenv("CDA_HOST", "https://example.test")

    csv2_main = importlib.import_module("cwmscli.commands.csv2cwms.__main__")
    tz = csv2_main.safe_zoneinfo("UTC")

    file_data = {
        "header": ["Time", "Headwater"],
        "data": {
            int(datetime(2025, 3, 25, 12, 7, tzinfo=tz).timestamp()): [
                "2025-03-25 12:07",
                "10.0",
            ],
            int(datetime(2025, 3, 25, 12, 24, tzinfo=tz).timestamp()): [
                "2025-03-25 12:24",
                "20.0",
            ],
        },
        "source_timezone": tz,
    }
    config = {
        "round_to_nearest": True,
        "use_if_multiple": "error",
        "input_files": {
            "BROK": {
                "timeseries": {
                    "BROK.Elev.Inst.1Hour.0.Rev-SCADA-cda": {
                        "columns": "Headwater",
                        "units": "ft",
                        "precision": 2,
                    }
                }
            }
        },
    }

    with pytest.raises(ValueError) as excinfo:
        csv2_main.load_timeseries(file_data, "BROK", config)

    assert "Multiple values found for timeseries" in str(excinfo.value)
