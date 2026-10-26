import sys

import click

from cwmscli.utils.interaction import is_non_interactive
from cwmscli.utils.version_cli import version_output_allows_color


class _Stream:
    def __init__(self, tty: bool):
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty


def _clear_headless_environment(monkeypatch):
    for name in (
        "CWMS_CLI_NON_INTERACTIVE",
        "CI",
        "GITHUB_ACTIONS",
        "TF_BUILD",
        "BUILD_BUILDID",
        "JENKINS_URL",
        "TEAMCITY_VERSION",
        "BUILDKITE",
        "CIRCLECI",
    ):
        monkeypatch.delenv(name, raising=False)


def test_non_tty_standard_input_is_non_interactive(monkeypatch):
    _clear_headless_environment(monkeypatch)
    monkeypatch.setattr(sys, "stdin", _Stream(False))

    assert is_non_interactive() is True


def test_ci_environment_is_non_interactive_with_tty(monkeypatch):
    _clear_headless_environment(monkeypatch)
    monkeypatch.setattr(sys, "stdin", _Stream(True))
    monkeypatch.setenv("CI", "true")

    assert is_non_interactive() is True


def test_explicit_interactive_mode_overrides_auto_detection(monkeypatch):
    _clear_headless_environment(monkeypatch)
    monkeypatch.setattr(sys, "stdin", _Stream(False))
    ctx = click.Context(click.Command("test"))
    ctx.params["non_interactive"] = False

    assert is_non_interactive(ctx) is False


def test_no_color_environment_disables_version_color(monkeypatch):
    monkeypatch.setattr(sys, "stdout", _Stream(True))
    monkeypatch.setenv("NO_COLOR", "")

    assert version_output_allows_color(no_color=False, log_file=None) is False
