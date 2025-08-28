import csv
import json
import os


def read_config(config_path):
    """Read the configuration file"""
    if not config_path.endswith(".json"):
        raise ValueError("Configuration file must be a JSON file.")
    with open(config_path, "r") as f:
        config = json.load(f)
    return config


def load_csv(file_path):
    """Load the CSV file and return the data."""
    if not file_path.endswith(".csv"):
        raise ValueError("Data file must be a CSV file.")
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"File not found: {file_path}. Be sure to set the path correctly in the configuration file. And use the argument --data-path to specify the directory containing the data files."
        )
    with open(file_path, "r") as f:
        reader = csv.reader(f)
        data = list(reader)
    return data
