import importlib.metadata as ilmd
import os
import sys

# Make cwms-cli importable for autodoc/sphinx-click
sys.path.insert(0, os.path.abspath(".."))

project = "cwms-cli"

# Get the installed package version without shadowing Sphinx's "version"
try:
    pkg_version = ilmd.version("cwms-cli")
except ilmd.PackageNotFoundError:
    pkg_version = "0.0.0"

release = pkg_version
version = pkg_version

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_click",
]

autosummary_generate = True
autodoc_typehints = "description"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

html_theme = "sphinx_rtd_theme"

linkcheck_ignore = [
    r"^http://localhost(:\d+)?/.*",
    r"^http://127\.0\.0\.1(:\d+)?/.*",
]
# autodoc_mock_imports = ["cwms", "pandas", "requests"]
