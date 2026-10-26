import os
import sys
from typing import Optional

import click

_FALSE_VALUES = {"0", "false", "no", "off"}
_CI_ENV_VARS = (
    "CI",
    "GITHUB_ACTIONS",
    "TF_BUILD",
    "BUILD_BUILDID",
    "JENKINS_URL",
    "TEAMCITY_VERSION",
    "BUILDKITE",
    "CIRCLECI",
)


def _enabled_environment_flag(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        return False
    return value.strip().lower() not in _FALSE_VALUES


def is_non_interactive(ctx: Optional[click.Context] = None) -> bool:
    """Return whether commands must avoid reading from standard input."""
    if ctx is None:
        ctx = click.get_current_context(silent=True)

    if ctx is not None:
        configured = ctx.find_root().params.get("non_interactive")
        if configured is not None:
            return bool(configured)

    if _enabled_environment_flag("CWMS_CLI_NON_INTERACTIVE"):
        return True
    if any(_enabled_environment_flag(name) for name in _CI_ENV_VARS):
        return True

    try:
        return not sys.stdin.isatty()
    except (AttributeError, OSError):
        return True
