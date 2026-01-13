# cwmscli/load/__main__.py
# Side-effect imports to register subcommands under `load_group`
from cwmscli.load.timeseries import timeseries as _timeseries
from cwmscli.load.location import location as _locations
from cwmscli.load.root import load_group  # export for callers
