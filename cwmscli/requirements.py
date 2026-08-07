# Shared minimum version requirements for optional dependencies used by
# the `@requires` decorator in `cwmscli.utils.deps`.

cwms = {
    "module": "cwms",
    "package": "cwms-python",
    "version": "1.0.7",
    "desc": "CWMS REST API Python client",
    "link": "https://github.com/HydrologicEngineeringCenter/cwms-python",
}

requests = {
    "module": "requests",
    "version": "2.30.0",
    "desc": "Required for HTTP API access",
}

dataretrieval = {
    "module": "dataretrieval",
    "package": "dataretrieval",
    "version": "1.0.10",
    "desc": "Loading hydrologic data from USGS",
    "link": "https://github.com/DOI-USGS/dataretrieval-python",
}

hec = {
    "module": "hec",
    "package": "hec-python-library",
    "version": "0.9.5",
    "desc": "Shared HEC time-series and data-store library",
    "link": "https://github.com/HydrologicEngineeringCenter/hec-python-library",
}

hecdss = {
    "module": "hecdss",
    "package": "hecdss",
    "version": "0.1.24",
    "desc": "HEC-DSS native Python bindings",
    "link": "https://github.com/HydrologicEngineeringCenter/hec-dss-python",
}
