csv2cwms Complete Config Example
================================

Below is a complete example of a configuration file for the ``csv2cwms`` command.
Not all options are required. 

See :doc:`csv2cwms <csv2cwms>` for the main command page. This page focuses on
the JSON config structure and the canonical example file.

Global options
--------------

The following top-level keys act as global defaults for all file entries under
``input_files`` unless a file-specific override is provided.

.. _csv2cwms-global-interval:

``interval``
~~~~~~~~~~~~

Global interval in seconds.

- When ``round_to_nearest`` is disabled, this controls the spacing used when
  generating output points.
- When ``round_to_nearest`` is enabled, this takes precedence as the rounding
  interval.
- If not set and rounding is disabled, the command attempts to determine the
  interval from the CSV timestamps.
- If not set and rounding is enabled, the command falls back to the interval
  parsed from the time series identifier. See
  :doc:`Supported interval identifiers <csv2cwms_intervals>`.

.. _csv2cwms-global-round-to-nearest:

``round_to_nearest``
~~~~~~~~~~~~~~~~~~~~

Global default for whether timestamps should be rounded into interval buckets
before output values are built.

- Default: ``False``
- File entries may override this with their own ``round_to_nearest`` setting.

.. _csv2cwms-global-use-if-multiple:

``use_if_multiple``
~~~~~~~~~~~~~~~~~~~

Global default for handling duplicate values when multiple rows land on the
same timestamp after parsing or rounding.

- Default: ``error``
- Valid values: ``error``, ``first``, ``last``, ``average``
- File entries may override this with their own ``use_if_multiple`` setting.

Configuration options
---------------------

.. list-table::
   :header-rows: 1
   :widths: 32 18 50

   * - Option
     - Required / Default
     - Description
   * - ``input_files``
     - Yes
     - Top-level mapping of input file keys to file-specific configuration blocks.
   * - ``interval``
     - No; auto-detect when not rounding
     - Global interval in seconds. Used for generated point spacing, and if ``round_to_nearest`` is enabled it takes precedence for rounding. Otherwise rounding falls back to :doc:`supported interval identifiers <csv2cwms_intervals>`.
   * - ``round_to_nearest``
     - No; ``False``
     - Global default for whether timestamps should be rounded into interval buckets before building output points.
   * - ``use_if_multiple``
     - No; ``error``
     - Global default duplicate-handling strategy when multiple rows land on the same timestamp. Valid values are ``error``, ``first``, ``last``, and ``average``.
   * - ``input_files: { file_key: {...} }``
     - Yes
     - Each file key contains one CSV input definition.
   * - ``{ data_path }``
     - Yes
     - Path to the CSV file for that input block.
   * - ``{ store_rule }``
     - No; ``REPLACE_ALL``
     - Store rule used when writing time series to CWMS.
   * - ``{ date_col }``
     - No; first CSV column
     - Header name of the CSV column containing the timestamp. If omitted, the first CSV column is assumed to be the timestamp column.
   * - ``{ date_format }``
     - No; fallback parser list
     - One date format string or a list of accepted date format strings used to parse timestamps from the CSV.
   * - ``{ round_to_nearest }``
     - No; inherits :ref:`csv2cwms-global-round-to-nearest`
     - Per-file override for ``round_to_nearest``.
   * - ``{ use_if_multiple }``
     - No; inherits :ref:`csv2cwms-global-use-if-multiple`
     - Per-file override for ``use_if_multiple``.
   * - ``{ timeseries }``
     - Yes
     - Mapping of CWMS time series identifiers to column/expression metadata.
   * - ``timeseries: { tsid: {...} }``
     - Yes
     - Each TSID key contains the mapping for one output time series.
   * - ``{ columns }``
     - Yes
     - CSV column name or expression used to compute the value written to that time series.
   * - ``{ units }``
     - No; ``""``
     - Units to send with the time series payload.
   * - ``{ precision }``
     - No; ``2``
     - Decimal precision used when rounding output values before storage.

Source file:
``cwmscli/commands/csv2cwms/examples/complete_config.json``

.. literalinclude:: ../../cwmscli/commands/csv2cwms/examples/complete_config.json
   :language: json

See also
--------

- :doc:`csv2cwms <csv2cwms>`
- :doc:`CLI reference <../cli>`
- :doc:`Supported interval identifiers <csv2cwms_intervals>`
