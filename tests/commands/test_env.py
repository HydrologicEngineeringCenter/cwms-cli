import os
from pathlib import Path

import pytest

from cwmscli.commands.env import get_envs_dir, read_env_file, write_env_file


def test_get_envs_dir_returns_path():
    envs_dir = get_envs_dir()
    assert isinstance(envs_dir, Path)
    assert "cwms-cli" in str(envs_dir)
    assert "envs" in str(envs_dir)


def test_write_and_read_env_file(tmp_path):
    env_file = tmp_path / "test.env"
    env_vars = {
        "ENVIRONMENT": "test",
        "CDA_API_ROOT": "https://example.com/cwms-data",
        "CDA_API_KEY": "secret123",
        "OFFICE": "SWT",
    }

    write_env_file(env_file, env_vars)

    assert env_file.exists()
    read_vars = read_env_file(env_file)

    assert read_vars == env_vars


def test_read_env_file_skips_comments(tmp_path):
    env_file = tmp_path / "test.env"
    env_file.write_text(
        "# This is a comment\n"
        "ENVIRONMENT=test\n"
        "\n"
        "# Another comment\n"
        "CDA_API_ROOT=https://example.com\n"
    )

    env_vars = read_env_file(env_file)

    assert env_vars == {
        "ENVIRONMENT": "test",
        "CDA_API_ROOT": "https://example.com",
    }


def test_read_env_file_handles_equals_in_value(tmp_path):
    env_file = tmp_path / "test.env"
    env_file.write_text("CDA_API_ROOT=https://example.com?param=value\n")

    env_vars = read_env_file(env_file)

    assert env_vars["CDA_API_ROOT"] == "https://example.com?param=value"


def test_read_env_file_nonexistent_returns_empty_dict(tmp_path):
    env_file = tmp_path / "nonexistent.env"
    env_vars = read_env_file(env_file)

    assert env_vars == {}


def test_write_env_file_creates_parent_dirs(tmp_path):
    env_file = tmp_path / "nested" / "dir" / "test.env"
    env_vars = {"ENVIRONMENT": "test"}

    write_env_file(env_file, env_vars)

    assert env_file.exists()
    assert env_file.parent.exists()


def test_write_env_file_sets_permissions(tmp_path):
    env_file = tmp_path / "test.env"
    env_vars = {"CDA_API_KEY": "secret"}

    write_env_file(env_file, env_vars)

    if os.name != "nt":
        stat_info = env_file.stat()
        mode = stat_info.st_mode & 0o777
        assert mode == 0o600
