# A file containing shared minimum version requirements for dependencies
# used by the `@requires` decorator in `cwmscli.utils.deps`.


cwms = {
    "module": "cwms",
    "package": "cwms-python",
    "version": "0.8.0",
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
