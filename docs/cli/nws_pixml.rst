NWS PI-XML loader
==================

Use ``cwms-cli nws pixml`` to load an NWS/RFC Delft-FEWS PI-XML forecast
product into a CWMS database.  Behavior—parameter mapping, timeseries-group
overrides, versioning, and issued-time tracking—is driven by a JSON config
file or a config blob stored in CDA.

For installation and first-run setup, see :doc:`Installation and Setup <setup>`.

Overview
--------

``nws pixml`` supports:

- loading a single PI-XML file or URL (``.gz``/``.zip`` auto-unzipped)
- config-driven NWS→CWMS parameter mapping
- TSID resolution via timeseries-group alias override with built fallback
- run selection by filename pattern (e.g. base / auto / CRF)
- per-run versioning control (versioned or unversioned)
- issued-time tracking via a consolidated JSON blob

Quick start
-----------

With ``CDA_API_ROOT``, ``CDA_API_KEY``, and ``OFFICE`` already set in your
environment (the typical setup) and a ``CONFIG_PIXML`` blob uploaded to your
office, the minimal invocation is:

.. code-block:: bash

   cwms-cli nws pixml -i forecast.xml

For a dry run (parse and resolve everything, but make no API writes):

.. code-block:: bash

   cwms-cli nws pixml -i forecast.xml --dry-run

Config resolution
-----------------

The loader resolves its JSON config from the first source that matches:

1. ``--config`` — a local JSON file path
2. ``--config-blob`` — a blob ID to fetch from CDA
3. **Automatic** — if neither flag is given, the loader fetches the blob
   ``CONFIG_PIXML`` from the target office

``--config`` and ``--config-blob`` are mutually exclusive.

Uploading a config blob
~~~~~~~~~~~~~~~~~~~~~~~

To store your office config as a blob so the loader finds it automatically:

.. code-block:: bash

   cwms-cli blob upload \
     --input-file configs/mvp.json \
     --blob-id CONFIG_PIXML \
     --media-type application/json \
     -o MVP

On subsequent updates, add ``--overwrite``:

.. code-block:: bash

   cwms-cli blob upload \
     --input-file configs/mvp.json \
     --blob-id CONFIG_PIXML \
     --media-type application/json \
     --overwrite \
     -o MVP

No office prefix is needed in the blob ID—blobs are already scoped to their
owning office on the CDA side.

See :doc:`Blob commands <blob>` for more on ``blob upload``.

Config structure
----------------

The config is a JSON object.  See the example configs shipped in
``docs/nws/mvp.example.json`` and ``docs/nws/mvm.example.json``.

Top-level keys:

- ``office`` — CWMS office ID (e.g. ``MVP``, ``MVM``)
- ``pi_namespace`` — XML namespace of the PI-XML document
- ``location_alias_groups[]`` — location alias groups used to resolve NWS
  location IDs to CWMS location IDs; later groups override earlier ones
- ``timeseries_group`` — the TS group used for alias-based TSID override
- ``parameter_map`` — NWS parameter → CWMS parameter name mapping
  (e.g. ``SQIN`` → ``Flow-Sim``)
- ``param_type_rules[]`` — rules that set type and duration when the CWMS
  parameter name matches a substring (e.g. ``Precip`` → ``Total``/``6Hours``)
- ``default_type``, ``default_duration`` — fallback type and duration
- ``runs[]`` — run definitions matched top-to-bottom by filename pattern;
  the last entry should have ``{"match": {"default": true}}``
- ``issued_time`` — issued-time blob configuration
- ``watersheds`` — NCRFC watershed key → label + CWMS watershed mapping

Run configuration
~~~~~~~~~~~~~~~~~

Each run entry controls:

- ``match`` — how to match the run (``filename_contains`` or ``default``)
- ``version_part`` — the version segment of the TSID
- ``versioned`` — whether to write a versioned time series
- ``version_source`` — where to get the version date
  (``filename_timestamp``, ``creation_date``, or ``forecast_date``)
- ``version_snap_time`` — snap the version date to this time
- ``issued_slot`` — which issued-time slot to update (``base``, ``crf``,
  ``auto``)

TSID resolution
~~~~~~~~~~~~~~~

For each series in the PI-XML:

1. **Alias override** — build a key from ``alias_key_template`` (e.g.
   ``{locationId}.{parameterId}``), look it up in the configured timeseries
   group.  If the run defines a ``version_part``, swap it into the 6th TSID
   segment so one alias serves base/auto/CRF.
2. **Built fallback** — construct
   ``{cwms_loc}.{param}.{type}.{interval}.{duration}.{version_part}`` from
   the mapped parameter, derived interval, and configured defaults.
   Unknown parameters, unresolved locations, and underivable intervals are
   warned and skipped.

Environment variables
---------------------

The following environment variables are recognized:

- ``OFFICE`` — default value for ``-o/--office``
- ``CDA_API_ROOT`` — default value for ``-a/--api-root``
- ``CDA_API_KEY`` — default value for ``-k/--api-key``

Example: MVP setup
------------------

.. code-block:: bash

   # One-time: upload the config blob
   cwms-cli blob upload \
     --input-file configs/mvp.json \
     --blob-id CONFIG_PIXML \
     --media-type application/json \
     -o MVP

   # Dry run (CDA_API_ROOT, CDA_API_KEY, and OFFICE are already in the environment)
   cwms-cli nws pixml -i MSR_main_m10_mississippi_river.xml --dry-run

   # Live run
   cwms-cli nws pixml -i MSR_main_m10_mississippi_river.xml

CLI Reference
-------------

.. click:: cwmscli.nws:nws_pixml
   :prog: cwms-cli nws pixml
   :nested: full

See also
--------

- :doc:`CLI reference <../cli>`
- :doc:`Blob commands <blob>`
- :doc:`Common API Arguments <api_arguments>`
- :doc:`Installation and Setup <setup>`
