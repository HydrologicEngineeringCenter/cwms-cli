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
pip install cwms-cli --upgrade
```

Or as of version `0.3.0+`
```sh
cwms-cli update
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
