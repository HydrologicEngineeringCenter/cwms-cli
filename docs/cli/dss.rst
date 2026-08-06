DSS time-series transfers
=========================

Install the optional dependencies
---------------------------------

HEC-DSS support is optional:

.. code-block:: console

   pip install "cwms-cli[dss]"

The native ``hecdss`` library is not currently available in macOS Mach-O
format. DSS file operations are therefore not supported on macOS.

.. _dss-commands:

Commands
--------

Use ``dss import`` to store DSS time series in CWMS through CDA, and
``dss export`` to write CWMS time series to a DSS file:

.. code-block:: console

   cwms-cli dss import --office SWT --api-root http://localhost:8081/cwms-data/ --dss-file archive.dss --lookback-hours 24
   cwms-cli dss export --office SWT --api-root https://cwms-data.usace.army.mil/cwms-data/ --dss-file extract.dss --lookback-hours 24 --filter-file tsids.txt

Migrating from the legacy scripts
---------------------------------

Here are a series of arguments that are mapped from the legacy ``dss2cwms.py``
and ``cwms2dss.py`` scripts to the current ``cwms-cli dss`` commands.

.. list-table:: Legacy-to-current command mapping
   :header-rows: 1
   :widths: 35 65

   * - Legacy form
     - Current form
   * - ``dss2cwms``
     - :ref:`cwms-cli dss import <dss-commands>`
   * - ``cwms2dss``
     - :ref:`cwms-cli dss export <dss-commands>`
   * - ``-o=<office>``
     - :doc:`--office <api_arguments>` ``<office>``
   * - ``-dss=<file>``
     - :ref:`--dss-file <dss-commands>` ``<file>``
   * - ``-f=<file>``
     - :ref:`--mapping-file <dss-mappings-filters>` ``<file>``
   * - ``-f2=<file>``
     - :ref:`--filter-file <dss-mappings-filters>` ``<file>``
   * - ``-p=<hours>``
     - :ref:`--lookback-hours <dss-authentication-time-windows>` ``<hours>``,
       or use :ref:`--start and --end <dss-authentication-time-windows>`
   * - ``-v=<0|1|2>``
     - :ref:`--verbosity <dss-commands>` ``<0|1|2>``
   * - ``-l=<directory>``
     - :ref:`--log-dir <dss-commands>` ``<directory>``
   * - ``-tz=<time-zone>``
     - :ref:`--dss-time-zone <dss-examples>` ``<time-zone>`` on
       ``dss export``
   * - ``-db=<file>``
     - Use :doc:`--api-root and the shared CDA authentication options
       <api_arguments>`; direct database connections are not supported
   * - ``-m`` or ``-id=<identifier>``
     - No replacement; see :ref:`Limitations <dss-limitations>`

.. _dss-examples:

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
     --end 2026-07-26T02:00:00Z \
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
     --end 2026-07-26T02:00:00Z

Add ``--dry-run`` to either command to perform retrieval, parsing, mapping,
and validation without opening the destination for writing.

.. _dss-authentication-time-windows:

Authentication and time windows
-------------------------------

Use ``cwms-cli login`` for a saved sign-in, or pass ``--api-key`` /
``--api-key-loc``. ``CDA_API_ROOT``, ``CDA_API_KEY``, and ``OFFICE`` are also
supported.

Every batch requires either ``--lookback-hours`` or both ``--start`` and
``--end``. Naive ISO-8601 values are interpreted as UTC. ``--dry-run`` reads,
maps, converts, and validates series without opening the destination for
writing.

.. _dss-mappings-filters:

Mappings and filters
--------------------

``--mapping-file`` and ``--filter-file`` are mutually exclusive. Blank lines
and lines beginning with ``#`` are ignored.

DSS-to-CWMS mapping rows use the following format. The downloadable import
sample contains:

.. code-block:: text

   # DSS pathname,CWMS TSID,CWMS unit,factor
   /CWMS-CLI/AARK/FLOW--INST--0//1HOUR/CCP-REV/,AARK.Flow.Inst.1Hour.0.Ccp-Rev,cms,1

CWMS-to-DSS mapping rows use the following format. The downloadable export
sample contains:

.. code-block:: text

   # CWMS TSID,DSS pathname,CWMS unit,factor,DSS unit
   AARK.Flow.Inst.1Hour.0.Ccp-Rev,/CWMS-CLI/AARK/FLOW--INST--0//1HOUR/CCP-REV/,cms,1,CMS

``$LOC`` may be used in both the DSS B-part and CWMS location part. Filter
files contain case-insensitive ``*`` and ``?`` wildcard patterns. Without a
mapping or filter, all cataloged time series are transferred using the
automatic round-trip pathname convention.

.. _dss-limitations:

Limitations
-----------

This release is batch-only. Unsupported modes are omitted from command help.
If supplied, they return migration guidance and a link to
`submit a new issue <https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/new>`_.
The commands do not create missing CWMS locations or propagate deletes and
renames.
