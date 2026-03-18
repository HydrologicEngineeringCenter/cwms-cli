csv2cwms
========

Use ``cwms-cli csv2cwms`` to load CSV time series data into `CWMS Data API (CDA) <https://cwms-data.usace.army.mil/cwms-data>`_ with a user defined JSON
configuration file.

This page is the dedicated documentation entry for the command. For a complete
config example, see :doc:`Complete config example <csv2cwms_complete_config>`.

  - For the JSON config reference, global defaults, and option table, start there.

  - For installation and first-run setup, see :doc:`Installation and Setup <setup>`.

Overview
--------

``csv2cwms`` supports:

- mapping one or more CSV columns into CWMS time series
- optional expressions across CSV value columns (i.e. column4+column5 into TSID)
- configurable duplicate handling with ``use_if_multiple``
- optional timestamp rounding with ``round_to_nearest``
- optional timestamp-column selection with ``date_col``

Setup and run
-------------

For installation, dependency setup, shared API arguments, the canonical config
example, and a real working sample run, see :doc:`Installation and Setup <setup>`.

For the JSON config structure itself, see
:doc:`Complete config example <csv2cwms_complete_config>`.

Common issues
-------------

If you are having trouble running ``csv2cwms``:

- Use the top-level ``cwms-cli --log-level`` option to increase logging detail.
  See :doc:`Common API Arguments <api_arguments>`.
- Confirm the shared CDA API inputs are set correctly. See
  :doc:`Common API Arguments <api_arguments>`.
- Confirm the JSON config matches the current ``input_files`` / ``data_path``
  structure. See :doc:`Complete config example <csv2cwms_complete_config>`.
- Verify the source CSV timestamps are in the timezone you are passing with
  ``--timezone``.

Important config behavior
-------------------------

- By default, the timestamp is assumed to be in the first CSV column.
- Set ``date_col`` to the CSV header name when the timestamp is in a different column.
- CSV rows whose first non-whitespace character is ``#`` are ignored automatically.
- The default timezone is ``GMT``.
- If ``round_to_nearest`` is enabled, config file ``interval`` takes precedence.
- If ``interval`` is not configured, rounding falls back to the interval parsed
  from the CWMS time series ``interval`` part. See
  :doc:`Supported interval identifiers <csv2cwms_intervals>` for the exact
  accepted values. Read the `Time Series Docs <https://cwms-database.readthedocs.io/en/latest/naming.html#time-series>`_
  for more on TSID structure.
- If multiple rows land in the same rounded timestamp, ``use_if_multiple``
  controls whether the first, last, average, or an error is used. Error is the default behavior.

Timezone handling
-----------------

The ``--timezone`` option defaults to ``GMT``.

Set ``--timezone`` when the timestamps in the CSV represent local clock time
instead of GMT/UTC. This matters because ``csv2cwms`` uses that timezone when:

- parsing timestamp strings from the CSV
- converting parsed timestamps into epoch values
- rounding timestamps into interval buckets

If the CSV timestamps are local plant, office, or regional times and you leave
the timezone at the default ``GMT``, the stored times can be shifted by the
wrong UTC offset. Set a real zone such as ``America/Chicago`` when the source
CSV was produced in that local timezone.

Quality codes
-------------

``csv2cwms`` currently emits a simple quality code for each generated point:

- ``3`` when the value is present
- ``5`` when the value is missing and the generated point is a gap

This is the behavior currently visible in debug output when the command logs the
generated time series points. In other words, if debug logging shows a line like
``[TSID] 2025-03-25 12:00:00 -> 20.0 (quality: 3)``, that trailing integer is
the quality code that will be written for that point.

Canonical Example
-----------------

.. literalinclude:: ../../cwmscli/commands/csv2cwms/examples/complete_config.json
   :language: json

For a dedicated page showing only the canonical config example, see
:doc:`Complete config example <csv2cwms_complete_config>`.

CLI Reference
-------------

.. click:: cwmscli.commands.commands_cwms:csv2cwms_cmd
   :prog: cwms-cli csv2cwms
   :nested: full

See also
--------

- :doc:`CLI reference <../cli>`
- :doc:`Installation and Setup <setup>`
- :doc:`Common API Arguments <api_arguments>`
- :doc:`Supported interval identifiers <csv2cwms_intervals>`
