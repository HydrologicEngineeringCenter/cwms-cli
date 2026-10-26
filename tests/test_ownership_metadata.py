from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.9/3.10
    import tomli as tomllib

from cwmscli.__main__ import cli
from cwmscli._generated.ownership_data import OWNERSHIP_DATA

ROOT = Path(__file__).resolve().parents[1]


def _command_paths(command, path=("cwms-cli",)):
    yield " ".join(path)
    for name, subcommand in getattr(command, "commands", {}).items():
        yield from _command_paths(subcommand, path + (name,))


def test_configured_cli_ownership_references_live_commands():
    live_commands = set(_command_paths(cli))
    configured_commands = set(OWNERSHIP_DATA["commands"])

    assert configured_commands <= live_commands, (
        "Maintainer assignments reference commands that no longer exist: "
        f"{sorted(configured_commands - live_commands)}"
    )


def test_codeowners_rules_reference_live_paths():
    with (ROOT / "maintainers.toml").open("rb") as maintainers_file:
        data = tomllib.load(maintainers_file)

    dead_patterns = []
    for rule in data["codeowners"]["rule"]:
        pattern = rule["pattern"]
        if pattern == "*":
            continue

        repository_pattern = pattern.lstrip("/").rstrip("/")
        if not any(ROOT.glob(repository_pattern)):
            dead_patterns.append(pattern)

    assert not dead_patterns, (
        "CODEOWNERS rules reference paths that no longer exist: " f"{dead_patterns}"
    )
