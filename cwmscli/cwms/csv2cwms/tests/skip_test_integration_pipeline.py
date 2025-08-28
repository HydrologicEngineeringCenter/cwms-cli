import json
import os

from scada_ts import __main__ as main
from utils.dateutils import parse_date
from utils.fileio import load_csv, read_config


def test_brok_pipeline_matches_expected():
    # Setup paths to our test files
    base = os.path.join(os.path.dirname(__file__), "data")
    csv_path = os.path.join(base, "sample_brok.csv")
    config_path = os.path.join(base, "sample_config.json")
    expected_path = os.path.join(base, "expected_brok_output.json")

    # Load all of our test files
    config = read_config(config_path)
    raw_csv = load_csv(csv_path)
    header = raw_csv[0]
    rows = raw_csv[1:]

    # Load the data into a dictionary with timestamps as keys
    parsed_data = {}
    for row in rows:
        dt = parse_date(row[0])
        parsed_data[int(dt.timestamp())] = row

    file_data = {"header": header, "data": parsed_data}

    actual = main.load_timeseries(file_data, "BROK", config)

    with open(expected_path) as f:
        expected = json.load(f)

    assert actual == expected
