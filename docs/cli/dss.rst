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

   cwms-cli dss import -o SWT -a http://localhost:8081/cwms-data/ -dss archive.dss -p 24
   cwms-cli dss export -o SWT -a https://cwms-data.usace.army.mil/cwms-data/ -dss extract.dss -p 24 -f2 tsids.txt

The installed ``dss2cwms`` and ``cwms2dss`` commands accept the same
direction-specific options for compatibility with legacy jobs.

Examples
--------

These examples use the real public SWT time series
``AARK.Flow.Inst.1Hour.0.Ccp-Rev``. Download the
:download:`CWMS-to-DSS export mapping <../examples/dss-export-mapping.csv>`
and the matching
:download:`DSS-to-CWMS import mapping <../examples/dss-import-mapping.csv>`.

First export a fixed public-CDA window to DSS:

.. code-block:: console

   cwms-cli dss export \
     --office SWT \
     --api-root https://cwms-data.usace.army.mil/cwms-data/ \
     --dss-file aark-flow.dss \
     --mapping-file dss-export-mapping.csv \
     --start 2026-07-26T00:00:00Z \
     --end 2026-07-27T07:00:00Z \
     --dss-time-zone US/Central

Then import the DSS record into a writable CDA instance. The ``AARK``
location and time-series identifier must already exist because this command
does not create locations or identifiers:

.. code-block:: console

   cwms-cli dss import \
     --office SWT \
     --api-root http://localhost:8081/cwms-data/ \
     --dss-file aark-flow.dss \
     --mapping-file dss-import-mapping.csv \
     --start 2026-07-26T00:00:00Z \
     --end 2026-07-27T07:00:00Z

Add ``--dry-run`` to either command to perform retrieval, parsing, mapping,
and validation without opening the destination for writing.

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

DSS-to-CWMS mapping rows retain the legacy format. The downloadable import
sample contains:

.. code-block:: text

   # DSS pathname,CWMS TSID,CWMS unit,factor
   /CWMS-CLI/AARK/FLOW--INST--0//1HOUR/CCP-REV/,AARK.Flow.Inst.1Hour.0.Ccp-Rev,cms,1

CWMS-to-DSS mapping rows retain the legacy format. The downloadable export
sample contains:

.. code-block:: text

   # CWMS TSID,DSS pathname,CWMS unit,factor,DSS unit
   AARK.Flow.Inst.1Hour.0.Ccp-Rev,/CWMS-CLI/AARK/FLOW--INST--0//1HOUR/CCP-REV/,cms,1,CMS

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
