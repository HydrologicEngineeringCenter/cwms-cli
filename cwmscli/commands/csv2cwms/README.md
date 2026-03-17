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
- Allow specifying an optional `date_col` when the timestamp is not the first CSV column
- Allow mathematical operations across multiple columns and storing into one timeseries
- Store one column of data with a user-specified precision and units to a timeseries identifier
- Allow choosing how duplicate values are handled with `use_if_multiple` (`first`, `last`, `average`, or `error`)
- Dry runs to test what data might look like prior to database storage
- Verbose logging via the -v flag
- Colored terminal output for user readability

## Rounding And Duplicate Handling

When `round_to_nearest` is not enabled (not specified/False), CSV timestamps are used as they appear in the file. The tool does not force timestamps onto the interval implied by the CWMS timeseries name in that mode.

When `round_to_nearest` is enabled (in the config and set to True), interval precedence is:

- Use the configured `interval` value first, if present. This value is in seconds.
- If `interval` is not configured, fall back to the interval parsed from the timeseries name such as `1Hour` or `15Minutes`.

If multiple CSV rows collapse into the same timestamp, `use_if_multiple` controls which value is kept:

- `error`: [DEFAULT] raise an error instead of choosing
- `first`: keep the first value encountered
- `last`: keep the last value encountered
- `average`: average the numeric values

This matters most when `round_to_nearest` is enabled, because multiple raw timestamps can land in the same rounded interval bucket.

## Timestamp Column

By default, `csv2cwms` assumes the timestamp is in the first CSV column.

If your CSV places the timestamp in a different column, set `date_col` in the input file config to the CSV header name for that timestamp column.

Example:

```json
{
  "input_files": {
    "BROK": {
      "data_path": "path/to/file.csv",
      "date_col": "ObservedAt",
      "date_format": "%Y-%m-%d %H:%M",
      "timeseries": {
        "BROK.Elev.Inst.15Minutes.0.Rev-SCADA-cda": {
          "columns": "Headwater",
          "units": "ft",
          "precision": 2
        }
      }
    }
  }
}
```
Where `ObservedAt` is the literal text in the first row header of the CSV file column. 

If the first column is not a parseable date and `date_col` is not set, you will get an error.
