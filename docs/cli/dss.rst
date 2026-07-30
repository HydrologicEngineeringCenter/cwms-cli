DSS time-series transfers
=========================

Install the optional dependencies
---------------------------------

HEC-DSS support is optional:

.. code-block:: console

   pip install "cwms-cli[dss]"

Commands
--------

Use ``dss import`` to store DSS time series in CWMS through CDA, and
``dss export`` to write CWMS time series to a DSS file:

.. code-block:: console

   cwms-cli dss import -o SWT -dss archive.dss -p 24
   cwms-cli dss export -o SWT -dss extract.dss -p 24 -f2 tsids.txt

The installed ``dss2cwms`` and ``cwms2dss`` commands accept the same
direction-specific options for compatibility with legacy jobs.

Authentication and time windows
-------------------------------

Use ``cwms-cli login`` for a saved sign-in, or pass ``--api-key`` /
``--api-key-loc``. ``CDA_API_ROOT``, ``CDA_API_KEY``, and ``OFFICE`` are also
supported.

Every batch requires either ``-p/--lookback-hours`` or both ``--start`` and
``--end``. Naive ISO-8601 values are interpreted as UTC. ``--dry-run`` reads,
maps, converts, and validates series without opening the destination for
writing.

Mappings and filters
--------------------

``-f/--mapping-file`` and ``-f2/--filter-file`` are mutually exclusive.
Blank lines and lines beginning with ``#`` are ignored.

DSS-to-CWMS mapping rows retain the legacy format:

.. code-block:: text

   pathname,tsid,CWMS_unit,factor

CWMS-to-DSS mapping rows retain the legacy format:

.. code-block:: text

   tsid,pathname,CWMS_unit,factor,DSS_unit

``$LOC`` may be used in both the DSS B-part and CWMS location part. Filter
files contain case-insensitive ``*`` and ``?`` wildcard patterns. Without a
mapping or filter, all cataloged time series are transferred using the legacy
round-trip pathname convention.

Compatibility limits
--------------------

This release is batch-only. Legacy ``-db`` direct Oracle connections, ``-m``
monitoring, and ``-id`` shadow-file checkpoints are recognized but return
migration guidance. The commands do not create missing CWMS locations or
propagate deletes and renames.
