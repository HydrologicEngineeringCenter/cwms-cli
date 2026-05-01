"""Credential storage using keyring for secure cross-platform credential management."""

import json
import os
from typing import Dict, List, Optional

import keyring
from keyring.errors import KeyringError


class CredentialStorageError(Exception):
    """Raised when credential storage operations fail."""

    pass


def is_keyring_available() -> bool:
    """
    Check if keyring backend is available and functional.

    Returns:
        True if keyring can be used, False otherwise
    """
    try:
        backend = keyring.get_keyring()
        # Test write/read/delete to ensure it actually works
        test_service = "cwms-cli-test"
        test_key = "__availability_test__"
        test_value = "test"

        keyring.set_password(test_service, test_key, test_value)
        result = keyring.get_password(test_service, test_key)
        keyring.delete_password(test_service, test_key)

        return result == test_value
    except (KeyringError, Exception):
        return False


def store_credential(service: str, key: str, value: str) -> None:
    """
    Store a credential in the system keyring.

    Args:
        service: Service name (e.g., "cwms-cli-env")
        key: Key/username for the credential
        value: Value/password to store

    Raises:
        CredentialStorageError: If keyring is not available
    """
    if not is_keyring_available():
        raise CredentialStorageError(
            "Secure credential storage (keyring) is not available.\n\n"
            "For headless/CI environments, set these environment variables instead:\n"
            '  export CDA_API_ROOT="https://..."\n'
            '  export CDA_API_KEY="your_key"\n'
            '  export OFFICE="SWT"\n\n'
            "For interactive systems, install a keyring backend:\n"
            "  Linux: Install gnome-keyring, kwallet, or python3-secretstorage\n"
            "  macOS: Uses Keychain (built-in)\n"
            "  Windows: Uses Credential Manager (built-in)"
        )

    try:
        keyring.set_password(service, key, value)
    except KeyringError as e:
        raise CredentialStorageError(f"Failed to store credential: {e}") from e


def get_credential(service: str, key: str) -> Optional[str]:
    """
    Retrieve a credential from the system keyring.

    Args:
        service: Service name (e.g., "cwms-cli-env")
        key: Key/username for the credential

    Returns:
        The credential value, or None if not found
    """
    if not is_keyring_available():
        return None

    try:
        return keyring.get_password(service, key)
    except KeyringError:
        return None


def delete_credential(service: str, key: str) -> None:
    """
    Delete a credential from the system keyring.

    Args:
        service: Service name (e.g., "cwms-cli-env")
        key: Key/username for the credential

    Raises:
        CredentialStorageError: If deletion fails
    """
    if not is_keyring_available():
        raise CredentialStorageError("Keyring is not available")

    try:
        keyring.delete_password(service, key)
    except KeyringError as e:
        raise CredentialStorageError(f"Failed to delete credential: {e}") from e


def list_stored_credentials(service_prefix: str) -> List[str]:
    """
    List credential keys for a given service prefix.

    Note: This functionality is limited by keyring backend capabilities.
    Some backends don't support enumeration, so this may return an empty list
    even if credentials exist.

    Args:
        service_prefix: Service name prefix (e.g., "cwms-cli-env")

    Returns:
        List of credential keys matching the service prefix
    """
    # Most keyring backends don't support enumeration
    # This is a limitation we document and work around
    # by having users explicitly name environments
    return []


# Environment-specific functions


def store_environment(env_name: str, config: Dict[str, str]) -> None:
    """
    Store environment configuration in keyring.

    Args:
        env_name: Name of the environment
        config: Dictionary of environment variables to store

    Raises:
        CredentialStorageError: If keyring is not available
    """
    service = f"cwms-cli-env:{env_name}"
    # Store the entire config as a JSON string
    config_json = json.dumps(config, sort_keys=True)
    store_credential(service, "config", config_json)


def get_environment(env_name: str) -> Optional[Dict[str, str]]:
    """
    Retrieve environment configuration from keyring.

    Args:
        env_name: Name of the environment

    Returns:
        Dictionary of environment variables, or None if not found
    """
    service = f"cwms-cli-env:{env_name}"
    config_json = get_credential(service, "config")

    if config_json:
        try:
            return json.loads(config_json)
        except json.JSONDecodeError:
            return None

    return None


def delete_environment(env_name: str) -> None:
    """
    Delete environment configuration from keyring.

    Args:
        env_name: Name of the environment

    Raises:
        CredentialStorageError: If deletion fails
    """
    service = f"cwms-cli-env:{env_name}"
    delete_credential(service, "config")


def get_environment_from_os_environ() -> Dict[str, str]:
    """
    Build environment config from OS environment variables.

    This is used as a fallback for headless/CI environments where keyring
    is not available. Only returns variables that are actually set.

    Returns:
        Dictionary of environment variables found in os.environ
    """
    env_vars = {}

    # Check for known environment variables
    if "CDA_API_ROOT" in os.environ:
        env_vars["CDA_API_ROOT"] = os.environ["CDA_API_ROOT"]

    if "CDA_API_KEY" in os.environ:
        env_vars["CDA_API_KEY"] = os.environ["CDA_API_KEY"]

    if "OFFICE" in os.environ:
        env_vars["OFFICE"] = os.environ["OFFICE"]

    if "ENVIRONMENT" in os.environ:
        env_vars["ENVIRONMENT"] = os.environ["ENVIRONMENT"]

    return env_vars


# Environment index management


def get_environment_index() -> List[str]:
    """
    Get list of all environment names from the index.

    Returns:
        List of environment names, or empty list if index doesn't exist
    """
    if not is_keyring_available():
        return []

    service = "cwms-cli-meta"
    index_json = get_credential(service, "environments")

    if index_json:
        try:
            return json.loads(index_json)
        except json.JSONDecodeError:
            return []

    return []


def add_to_environment_index(env_name: str) -> None:
    """
    Add an environment name to the index.

    Args:
        env_name: Name of the environment to add

    Raises:
        CredentialStorageError: If keyring is not available
    """
    if not is_keyring_available():
        raise CredentialStorageError("Keyring is not available")

    index = get_environment_index()
    if env_name not in index:
        index.append(env_name)
        index.sort()
        service = "cwms-cli-meta"
        store_credential(service, "environments", json.dumps(index))


def remove_from_environment_index(env_name: str) -> None:
    """
    Remove an environment name from the index.

    Args:
        env_name: Name of the environment to remove

    Raises:
        CredentialStorageError: If keyring is not available
    """
    if not is_keyring_available():
        raise CredentialStorageError("Keyring is not available")

    index = get_environment_index()
    if env_name in index:
        index.remove(env_name)
        service = "cwms-cli-meta"
        if index:
            store_credential(service, "environments", json.dumps(index))
        else:
            # If index is empty, delete it
            try:
                delete_credential(service, "environments")
            except CredentialStorageError:
                pass  # It's okay if it doesn't exist
