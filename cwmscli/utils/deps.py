import importlib
import importlib.metadata
import os

import click
from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion


def _pip_command():
    # Check OS to determine pip vs pip3
    if os.name == "nt":
        return "pip"
    # Avoid potential issues with multiple python (2/3) versions on Unix/Linux systems
    else:
        return "pip3"


def requires(*requirements):
    """Check that command dependencies are installed and in their supported range.

    Each requirement dictionary accepts:
      - module: importable module name.
      - package: distribution name, if different from the module name.
      - version: inclusive minimum version (optional).
      - max_version: exclusive upper version bound (optional).
      - desc: description included in missing-module errors (optional).
      - link: documentation URL (optional).

    For example, {"module": "cwms", "package": "cwms-python",
    "version": "1.0.7", "max_version": "2.0.0"} accepts >=1.0.7,<2.0.0.
    Requirements without max_version retain their minimum-only behavior.
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            missing = []
            version_issues = []

            for req in requirements:
                mod = req["module"]
                pkg = req.get("package", mod)
                constraints = []
                if req.get("version"):
                    constraints.append(f">={req['version']}")
                if req.get("max_version"):
                    constraints.append(f"<{req['max_version']}")
                version_range = ",".join(constraints)
                supported = SpecifierSet(version_range)
                install_target = f'"{pkg}{version_range}"' if version_range else pkg
                desc = req.get("desc")
                link = req.get("link")
                try:
                    importlib.import_module(mod)
                except ImportError:
                    msg = f"- `{mod}` (install: `{pkg}`)"
                    if desc:
                        msg += f" — {desc}"
                    if link:
                        msg += f" [docs]({link})"
                    missing.append((msg, install_target))
                    continue

                if version_range:
                    try:
                        actual_version = importlib.metadata.version(pkg)
                        # Preserve support for installed prereleases within the range;
                        # PEP 440 still excludes prereleases of the upper boundary.
                        if not supported.contains(actual_version, prereleases=True):
                            version_issues.append(
                                f"- python package `{pkg}` version `{actual_version}` found, "
                                f"but this command requires `{version_range}`.\n"
                                f"  Upgrade cwms-cli to check for support for newer dependencies:\n"
                                f"    {_pip_command()} install --upgrade cwms-cli\n"
                                f"  Or install a version supported by this command:\n"
                                f"    {_pip_command()} install {install_target}"
                            )
                    except importlib.metadata.PackageNotFoundError:
                        version_issues.append(
                            f"- `{pkg}` is installed but version could not be verified"
                        )
                    except InvalidVersion:
                        version_issues.append(
                            f"- `{pkg}` has an invalid version `{actual_version}`; "
                            f"version could not be verified.\n"
                            f"  Reinstall a supported version:\n"
                            f"    {_pip_command()} install --force-reinstall {install_target}"
                        )

            if missing or version_issues:
                error_lines = []
                if missing:
                    error_lines.append("Missing module(s):")
                    for msg, _ in missing:
                        error_lines.append(msg)
                    install_cmd = f"{_pip_command()} install " + " ".join(
                        target for _, target in missing
                    )
                    error_lines.append(
                        f"\nInstall missing packages:\n    {install_cmd}"
                    )
                if version_issues:
                    error_lines.append("\nVersion issues:")
                    error_lines.extend(version_issues)
                raise click.ClickException("\n".join(error_lines))

            return func(*args, **kwargs)

        return wrapper

    return decorator
