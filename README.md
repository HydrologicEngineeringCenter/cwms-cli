# cwms-cli

command line utilities used for Corps Water Management Systems (CWMS) processes

[![Docs](https://readthedocs.org/projects/cwms-cli/badge/?version=latest)](https://cwms-cli.readthedocs.io/en/latest/) - 📖 Read the docs: https://cwms-cli.readthedocs.io/en/latest/

## Install

```sh
pip install git+https://github.com/HydrologicEngineeringCenter/cwms-cli.git@main
```

## Command line implementation

```sh
cwms-cli --help
```

## run from within python
```python
from cwmscli.usgs.getusgs_cda import getusgs_cda
from cwmscli.usgs.getusgs_measurements_cda import getusgs_measurements_cda
from cwmscli.usgs.getUSGS_ratings_cda import getusgs_rating_cda
```
