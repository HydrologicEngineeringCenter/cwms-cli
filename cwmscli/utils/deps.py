import importlib
import importlib.metadata

import click


def requires(*requirements):
    """
    Decorator that ensures required Python modules are installed and meet optional minimum version constraints.

    Parameters:
        *requirements: One or more dictionaries describing a module requirement.
            Each dictionary may contain the following keys:

            - module (str): The importable module name (e.g., "requests").

            - package (str, optional): The name of the package to install via pip.
              Use this if the pip install name differs from the import name
              (e.g., module="cwms", package="cwms-python").

            - version (str, optional): A minimum required version string (e.g., "2.30.0").

            - desc (str, optional): A short description of what the module is or why it's needed.
              Included in the error message to help users understand the dependency.

            - link (str, optional): A URL pointing to documentation or the package's homepage.

    Example:
        @requires(
            {
                "module": "cwms",
                "package": "cwms-python",
                "version": "0.8.0",
                "desc": "CWMS REST API Python client",
                "link": "https://github.com/hydrologicengineeringcenter/cwms-python"
            },
            {
                "module": "requests",
                "version": "2.30.0",
                "desc": "Required for HTTP API access"
            }
        )
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            missing = []
            version_issues = []

            for req in requirements:
                mod = req["module"]
                pkg = req.get("package", mod)
                min_version = req.get("version")
                desc = req.get("desc")
                link = req.get("link")
                # Check if the provided requirement is already imported
                try:
                    importlib.import_module(mod)
                except ImportError:
                    msg = f"- `{mod}` (install: `{pkg}`)"
                    if desc:
                        msg += f" — {desc}"
                    if link:
                        msg += f" [docs]({link})"
                    missing.append((msg, pkg))
                    continue
                # Confirm the minimum version is met
                if min_version:
                    try:
                        actual_version = importlib.metadata.version(pkg)
                        if actual_version < min_version:
                            version_issues.append(
                                f"- `{pkg}` version `{actual_version}` found, "
                                f"but `{min_version}` or higher is required"
                            )
                    except importlib.metadata.PackageNotFoundError:
                        version_issues.append(
                            f"- `{pkg}` is installed but version could not be verified"
                        )
            # Build out the error response
            if missing or version_issues:
                error_lines = []
                if missing:
                    error_lines.append("Missing module(s):")
                    for msg, _ in missing:
                        error_lines.append(msg)
                    install_cmd = "pip install " + " ".join(pkg for _, pkg in missing)
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
