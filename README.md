# cwms-cli

A collection of scripts to create, read, update, list, and delete data through CWMS Data API (CDA) and other commonly used API in the US Army Corps of Engineers water management. CWMS-CLI wraps these API in a friendly to use terminal based interface.

[![Docs](https://readthedocs.org/projects/cwms-cli/badge/?version=latest)](https://cwms-cli.readthedocs.io/en/latest/cli.html#cwms-cli) - 📖 Read the docs: https://cwms-cli.readthedocs.io/en/latest/

## Install

```sh
pip3 install git+https://github.com/HydrologicEngineeringCenter/cwms-cli.git@main
```
Note: If you are on Windows OS, you may just need to use the command `pip`

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
