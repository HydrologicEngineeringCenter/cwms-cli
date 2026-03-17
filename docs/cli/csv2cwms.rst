csv2cwms
========

Use ``cwms-cli csv2cwms`` to load CSV time series data into [CWMS Data API (CDA)](https://cwms-data.usace.army.mil/cwms-data) from a JSON
configuration file.

This page is the dedicated documentation entry for the command. For a complete
config example, see
``cwmscli/commands/csv2cwms/examples/complete_config.json`` in the repository.

Overview
--------

``csv2cwms`` supports:

- mapping one or more CSV columns into CWMS time series
- optional expressions across CSV value columns (i.e. column4+column5 into TSID)
- configurable duplicate handling with ``use_if_multiple``
- optional timestamp rounding with ``round_to_nearest``
- optional timestamp-column selection with ``date_col``

Important config behavior
-------------------------

- By default, the timestamp is assumed to be in the first CSV column.
- Set ``date_col`` to the CSV header name when the timestamp is in a different column.
- If ``round_to_nearest`` is enabled, config file ``interval`` takes precedence.
- If ``interval`` is not configured, rounding falls back to the interval parsed
  from the CWMS time series 'interval' part. Read the [Time Series Docs](https://cwms-database.readthedocs.io/en/latest/naming.html#time-series) for more on interval parsing.
- If multiple rows land in the same rounded timestamp, ``use_if_multiple``
  controls whether the first, last, average, or an error is used. Error is the default behavior.

Canonical Example
-----------------

.. literalinclude:: ../../cwmscli/commands/csv2cwms/examples/complete_config.json
   :language: json

CLI Reference
-------------

.. click:: cwmscli.commands.commands_cwms:csv2cwms_cmd
   :prog: cwms-cli csv2cwms
   :nested: full

See also
--------

- :doc:`CLI reference <../cli>`
