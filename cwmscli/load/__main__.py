# cwmscli/load/__main__.py
# Side-effect imports to register subcommands under `load_group`
from . import location_group as _location_group
from . import locations as _locations
from .root import load_group  # export for callers
