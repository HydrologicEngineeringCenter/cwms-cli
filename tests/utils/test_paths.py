"""Tests for the shared per-user config-dir helper."""

from pathlib import Path

from cwmscli.utils.auth import default_token_file
from cwmscli.utils.env_store import envs_dir
from cwmscli.utils.paths import config_dir


def test_config_dir_uses_xdg_when_set(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_dir() == tmp_path / "cwms-cli"
    assert config_dir("envs") == tmp_path / "cwms-cli" / "envs"


def test_config_dir_falls_back_to_home_config(monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert config_dir("auth") == Path("~/.config").expanduser() / "cwms-cli" / "auth"


def test_config_dir_create_makes_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = config_dir("envs", create=True)
    assert path.is_dir()


def test_auth_and_env_share_one_root(monkeypatch, tmp_path):
    """Saved logins and named environments must live under the same root."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    token = default_token_file("federation-eams")
    envs = envs_dir()
    assert token.parent.parent == envs.parent
    assert token.parent.parent == tmp_path / "cwms-cli"
