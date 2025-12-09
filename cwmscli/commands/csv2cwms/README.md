# CSV2CWMS

Writes CSV timeseries data to CDA using a configuration file.

To View the Help: `cwms-cli csv2cwms --help`

## USAGE (--help)

Usage: cwms-cli csv2cwms [OPTIONS]

Store CSV TimeSeries data to CWMS using a config file

Options:
-o, --office TEXT Office to grab data for [required]
-a, --api_root TEXT Api Root for CDA. Can be user defined or placed
in a env variable CDA_API_ROOT [required]
-k, --api_key TEXT api key for CDA. Can be user defined or place in
env variable CDA_API_KEY. one of api_key or
api_key_loc are required
-l, --location TEXT Location ID. Use "-p=all" for all locations.
[default: all]
-lb, --lookback INTEGER Lookback period in HOURS [default: 120]
-v, --verbose Verbose logging
-c, --config PATH Path to JSON config file [required]
[default: all]
-lb, --lookback INTEGER Lookback period in HOURS [default: 120]
-v, --verbose Verbose logging
[default: all]
[default: all]
-lb, --lookback INTEGER Lookback period in HOURS [default: 120]
-v, --verbose Verbose logging
-c, --config PATH Path to JSON config file [required]
-df, --data-file TEXT Override CSV file (else use config)
--log TEXT Path to the log file.
-dp, --data-path DIRECTORY Directory where csv files are stored [default:
.]
--dry-run Log only (no HTTP calls)
--begin TEXT YYYY-MM-DDTHH:MM (local to --tz)
-tz, --timezone TEXT [default: GMT]
--ignore-ssl-errors Ignore TLS errors (testing only)
--version Show the version and exit.
--help Show this message and exit.

## Features

- Allow for specifying one or more date formats that might be seen per input csv file
- Allow mathematical operations across multiple columns and storing into one timeseries
- Store one column of data with a user-specified precision and units to a timeseries identifier
- Dry runs to test what data might look like prior to database storage
- Verbose logging via the -v flag
- Colored terminal output for user readability
