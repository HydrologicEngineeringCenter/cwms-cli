import importlib

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
