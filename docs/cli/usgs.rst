USGS Data Retrieval
===================

.. include:: ../_generated/maintainers/usgs.inc

``cwms-cli usgs`` retrieves USGS data and stores it in CWMS through CDA.
Configure :doc:`api_arguments` and install the optional packages:

.. code-block:: bash

   python -m pip install cwms-python dataretrieval

``dataretrieval`` is required for ratings and measurements. The examples below
assume ``CDA_API_ROOT`` and ``CDA_API_KEY`` are set for your target.
Timeseries, ratings, and measurements commands write immediately; they have
no ``--dry-run`` option.

Time-series values
------------------

Configure the office's time series in ``Data Acquisition / USGS TS Data
Acquisition`` and matching location aliases in ``Agency Aliases / USGS Station
Number``. The location aliases supply the USGS station numbers. A time-series
alias can select a USGS method; series without one use the default retrieval.

.. code-block:: bash

   cwms-cli usgs timeseries --office SWT --days-back 1

``--days-back`` accepts fractional days and defaults to one day. To restrict
retrieval to configured CWMS IDs, supply a comma-separated list:

.. code-block:: bash

   cwms-cli usgs timeseries --office SWT --days-back 7 --backfill "Example.Flow.Inst.15Minutes.0.USGS"

``--backfill`` filters configured IDs; it does not create the acquisition
configuration or automatically request the full period of record.

Ratings
-------

Ratings require active, auto-updating CWMS rating specifications with
``USGS-EXSA``, ``USGS-CORR``, or ``USGS-BASE`` in their descriptions, plus
matching ``USGS Station Number`` location aliases.

.. code-block:: bash

   cwms-cli usgs ratings --office SWT --days-back 1

Use ``--rating-subset "spec-id-1,spec-id-2"`` to limit eligible specifications.
``--days-back`` controls the search for recently updated USGS ratings.

To update existing rating specifications from a legacy ratings INI file:

.. code-block:: bash

   cwms-cli usgs ratings-ini-file-import --filename ratings.ini --dry-run

The INI supplies ``cwms_office``, rating IDs such as ``db_exsa``, and operations
such as ``store_exsa``. This command updates specification settings used by
``usgs ratings``; it does not retrieve rating curves. Its dry run reads CDA
specifications but does not update them. Remove ``--dry-run`` after review.

Measurements
------------

Configure locations in ``Data Acquisition / USGS Measurements`` and give
those locations aliases in ``Agency Aliases / USGS Station Number``.

.. code-block:: bash

   cwms-cli usgs measurements --office SWT --days-back-modified 2 --days-back-collected 365

For period-of-record backfills, use ``--backfill "05057200,05051300"`` with
USGS station numbers, or ``--backfill group`` for all configured sites.
Unlike the time-series command, measurement backfills take USGS IDs, not
CWMS time-series IDs.

See :doc:`../cli` for all options. If no eligible data is found, check the
office, group memberships, aliases, and requested subset before expanding
the retrieval window.
