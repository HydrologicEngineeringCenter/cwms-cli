import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cwmscli.commands.env import get_envs_dir


def test_get_envs_dir_returns_path():
    envs_dir = get_envs_dir()
    assert isinstance(envs_dir, Path)
    assert "cwms-cli" in str(envs_dir)
    assert "envs" in str(envs_dir)


# Test keyring-based environment management
@pytest.fixture
def mock_keyring():
    """Mock keyring module for testing."""
    with patch("cwmscli.utils.credentials.keyring") as mock:
        # Mock successful keyring operations
        mock.get_keyring.return_value = MagicMock()
        mock.get_password.return_value = None
        mock.set_password.return_value = None
        mock.delete_password.return_value = None
        yield mock


def test_store_and_get_environment(mock_keyring):
    """Test storing and retrieving environment configuration."""
    from cwmscli.utils.credentials import get_environment, store_environment

    env_name = "test-env"
    env_vars = {
        "ENVIRONMENT": "test",
        "CDA_API_ROOT": "https://example.com/cwms-data",
        "CDA_API_KEY": "secret123",
        "OFFICE": "SWT",
    }

    # Mock storage
    stored_data = {}

    def set_password(service, key, value):
        stored_data[f"{service}:{key}"] = value

    def get_password(service, key):
        return stored_data.get(f"{service}:{key}")

    mock_keyring.set_password.side_effect = set_password
    mock_keyring.get_password.side_effect = get_password

    # Store environment
    store_environment(env_name, env_vars)

    # Verify it was stored
    assert f"cwms-cli-env:{env_name}:config" in stored_data

    # Retrieve environment
    retrieved_vars = get_environment(env_name)
    assert retrieved_vars == env_vars


def test_delete_environment(mock_keyring):
    """Test deleting environment configuration."""
    from cwmscli.utils.credentials import (
        delete_environment,
        get_environment,
        store_environment,
    )

    env_name = "test-env"
    env_vars = {"ENVIRONMENT": "test", "CDA_API_ROOT": "https://example.com"}

    # Mock storage
    stored_data = {}

    def set_password(service, key, value):
        stored_data[f"{service}:{key}"] = value

    def get_password(service, key):
        return stored_data.get(f"{service}:{key}")

    def delete_password(service, key):
        stored_data.pop(f"{service}:{key}", None)

    mock_keyring.set_password.side_effect = set_password
    mock_keyring.get_password.side_effect = get_password
    mock_keyring.delete_password.side_effect = delete_password

    # Store and then delete
    store_environment(env_name, env_vars)
    delete_environment(env_name)

    # Verify it was deleted
    assert get_environment(env_name) is None


def test_get_environment_nonexistent_returns_none(mock_keyring):
    """Test retrieving non-existent environment returns None."""
    from cwmscli.utils.credentials import get_environment

    mock_keyring.get_password.return_value = None
    result = get_environment("nonexistent")
    assert result is None


def test_environment_index_management(mock_keyring):
    """Test adding and removing environments from the index."""
    from cwmscli.utils.credentials import (
        add_to_environment_index,
        get_environment_index,
        remove_from_environment_index,
    )

    # Mock storage
    stored_data = {}

    def set_password(service, key, value):
        stored_data[f"{service}:{key}"] = value

    def get_password(service, key):
        return stored_data.get(f"{service}:{key}")

    def delete_password(service, key):
        stored_data.pop(f"{service}:{key}", None)

    mock_keyring.set_password.side_effect = set_password
    mock_keyring.get_password.side_effect = get_password
    mock_keyring.delete_password.side_effect = delete_password

    # Initially empty
    assert get_environment_index() == []

    # Add environments
    add_to_environment_index("env1")
    add_to_environment_index("env2")
    assert sorted(get_environment_index()) == ["env1", "env2"]

    # Remove environment
    remove_from_environment_index("env1")
    assert get_environment_index() == ["env2"]


def test_get_environment_from_os_environ():
    """Test building environment config from OS environment variables."""
    from cwmscli.utils.credentials import get_environment_from_os_environ

    with patch.dict(
        os.environ,
        {
            "CDA_API_ROOT": "https://example.com/cwms-data",
            "CDA_API_KEY": "test-key",
            "OFFICE": "SWT",
            "ENVIRONMENT": "test",
        },
        clear=False,
    ):
        result = get_environment_from_os_environ()
        assert result == {
            "CDA_API_ROOT": "https://example.com/cwms-data",
            "CDA_API_KEY": "test-key",
            "OFFICE": "SWT",
            "ENVIRONMENT": "test",
        }


def test_get_environment_from_os_environ_partial():
    """Test building config with only some variables set."""
    from cwmscli.utils.credentials import get_environment_from_os_environ

    with patch.dict(
        os.environ,
        {
            "CDA_API_ROOT": "https://example.com/cwms-data",
            "OFFICE": "SWT",
        },
        clear=True,
    ):
        result = get_environment_from_os_environ()
        assert result == {
            "CDA_API_ROOT": "https://example.com/cwms-data",
            "OFFICE": "SWT",
        }
        assert "CDA_API_KEY" not in result
        assert "ENVIRONMENT" not in result


def test_is_keyring_available_success(mock_keyring):
    """Test keyring availability check when keyring works."""
    from cwmscli.utils.credentials import is_keyring_available

    # Mock successful keyring operations
    stored_value = None

    def set_password(service, key, value):
        nonlocal stored_value
        stored_value = value

    def get_password(service, key):
        return stored_value

    mock_keyring.set_password.side_effect = set_password
    mock_keyring.get_password.side_effect = get_password
    mock_keyring.delete_password.return_value = None

    assert is_keyring_available() is True


def test_is_keyring_available_failure(mock_keyring):
    """Test keyring availability check when keyring fails."""
    from keyring.errors import KeyringError

    from cwmscli.utils.credentials import is_keyring_available

    # Mock keyring failure
    mock_keyring.get_keyring.side_effect = KeyringError("No keyring available")

    assert is_keyring_available() is False


def test_store_environment_no_keyring():
    """Test storing environment when keyring is not available."""
    from cwmscli.utils.credentials import CredentialStorageError, store_environment

    with patch("cwmscli.utils.credentials.is_keyring_available", return_value=False):
        with pytest.raises(CredentialStorageError, match="Secure credential storage"):
            store_environment("test", {"CDA_API_ROOT": "https://example.com"})
