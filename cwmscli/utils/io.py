import logging
import os
from pathlib import Path


def write_to_file(file_path: str, data: str, create_dir: bool = False) -> None:
    """Writes data to a file at the specified path."""
    if not file_path:
        raise ValueError("You must specify a file path to write data to.")
    if not data:
        raise ValueError("No data provided to write to file.")
    if create_dir:
        Path(os.path.dirname(file_path)).mkdir(parents=True, exist_ok=True)
    with open(file_path, "w") as file:
        file.write(data)
    logging.info(f"Data written to file: {file_path}")
