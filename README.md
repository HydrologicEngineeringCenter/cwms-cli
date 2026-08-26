# cwms-cli

A collection of scripts to create, read, update, list, and delete data through CWMS Data API (CDA) and other commonly used API in the US Army Corps of Engineers water management. CWMS-CLI wraps these API in a friendly to use terminal based interface.

[![Docs](https://readthedocs.org/projects/cwms-cli/badge/?version=latest)](https://cwms-cli.readthedocs.io/en/latest/cli.html#cwms-cli) - 📖 Read the docs: https://cwms-cli.readthedocs.io/en/latest/

## Install

```sh
pip install cwms-cli
```
Note: You may need to run `python -m pip install cwms-cli` if PIP is not in your path.


### Update
```sh
python -m pip install --upgrade cwms-cli
```

Or as of version `0.3.0+`
```sh
cwms-cli update
```

`cwms-cli update` displays the Python executable, environment, package metadata
location, and editable project location when applicable before asking for
confirmation. It runs pip through the same Python interpreter that is running
`cwms-cli`, avoiding accidental updates to a different Python installation or
virtual environment.

To install a specific version:
```sh
cwms-cli update --target-version 0.7.1 --yes
```

## Command line implementation

View the help in terminal:
```sh
cwms-cli --help
```

## run from within python
```python
from cwmscli.usgs.getusgs_cda import getusgs_cda
from cwmscli.usgs.getusgs_measurements_cda import getusgs_measurements_cda
from cwmscli.usgs.getUSGS_ratings_cda import getusgs_rating_cda
```

## Development environment

The repository includes a Linux/Python 3.12 development container exercised by
a dedicated CI job. Open the repository with the VS Code Dev Containers
extension, or use the Dev Container CLI:

```sh
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . poetry run pytest -q
```

The container installs project dependencies with Poetry and uses
`/home/vscode/.venv`, so it does not reuse a host operating system's `.venv`.
Poetry itself is kept in a separate `/opt/poetry` environment. The workspace
root is also added to `PYTHONPATH`, so the checked-out source and local test
modules are available throughout a Codespace without copying them into the
image. Use the container for changes involving time zones, paths, native
libraries, or other operating-system-dependent behavior. Standard Python 3.9
and Python 3.12 installations remain covered by the existing CI matrix.
