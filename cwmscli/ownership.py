from __future__ import annotations

from cwmscli._generated.ownership_data import OWNERSHIP_DATA


def _command_candidates(command_path: str) -> list[str]:
    parts = command_path.split()
    candidates = [" ".join(parts[:i]) for i in range(len(parts), 0, -1)]
    return [candidate for candidate in candidates if candidate]


def get_command_maintainers(command_path: str) -> list[dict[str, str]]:
    commands = OWNERSHIP_DATA["commands"]
    for candidate in _command_candidates(command_path):
        if candidate in commands:
            return commands[candidate]
    return OWNERSHIP_DATA["default"]


def get_core_maintainer_emails() -> set[str]:
    return {person["email"] for person in OWNERSHIP_DATA["default"]}


def format_command_maintainers(command_path: str) -> str:
    maintainers = get_command_maintainers(command_path)
    return ", ".join(person["name"] for person in maintainers)
