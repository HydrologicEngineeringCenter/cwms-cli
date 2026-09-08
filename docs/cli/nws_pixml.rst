NWS PI-XML loader
==================

Use ``cwms-cli nws pixml`` to load forecast products exported by National
Weather Service (NWS) River Forecast Centers (RFCs) from the Community
Hydrologic Prediction System (CHPS). CHPS exports these products in Delft Flood
Early Warning System (Delft-FEWS) Published Interface XML (PI-XML) format.
Behavior—parameter mapping, timeseries-group overrides, versioning, and
issued-time tracking—is driven by a JSON config file or a config blob stored in
CDA.

.. warning::

   Follow the originating RFC's data-handling and dissemination requirements before sharing loaded data.

For installation and first-run setup, see :doc:`Installation and Setup <setup>`.

Overview
--------

``nws pixml`` supports:

- loading a single PI-XML file or URL (``.gz``/``.zip`` auto-unzipped)
- config-driven NWS→CWMS parameter mapping
- TSID resolution via timeseries-group alias override with optional built fallback
- run selection by filename pattern (e.g. base / auto / CRF)
- per-run versioning control (versioned or unversioned)
- issued-time tracking via a consolidated JSON blob

Quick start
-----------

With ``CDA_API_ROOT``, ``CDA_API_KEY``, and ``OFFICE`` already set in your
environment (:doc:`the typical setup <setup>`) and a ``CONFIG_PIXML`` blob
uploaded to your office, the minimal invocation is:

.. code-block:: bash

   cwms-cli nws pixml -i forecast.xml

For a dry run (parse and resolve everything, but make no API writes):

.. code-block:: bash

   cwms-cli nws pixml -i forecast.xml --dry-run

Config resolution
-----------------

The loader resolves its JSON config from the first source that matches:

1. ``--config`` — a local JSON file path
2. ``--config-blob-id`` — a blob ID to fetch from CDA
3. **Automatic** — if neither flag is given, the loader fetches the blob
   ``CONFIG_PIXML`` from the target office

``--config`` and ``--config-blob-id`` are mutually exclusive.

Uploading a config blob
~~~~~~~~~~~~~~~~~~~~~~~

``CONFIG_PIXML`` is the loader's hard-coded automatic lookup ID. The command
uses the generic :ref:`single-file blob upload <blob-single-file-upload>`
syntax; this example supplies the PI-XML-specific ID and JSON media type:

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

Config structure
----------------

The config is a JSON object. See the downloadable
:download:`MVP example config <../nws/mvp.example.json>` and
:download:`MVM example config <../nws/mvm.example.json>`.

These keys configure the cwms-cli loader; they are not part of PI-XML. The MVP
and MVM RFC products tested with this loader use the Delft-FEWS PI namespace
and time-series structure. See the Deltares `Delft-FEWS PI time-series schema
<https://fewsdocs.deltares.nl/schemas/version1.0/pi-schemas/pi_timeseries.xsd>`_
for the underlying format.

Array types below are JSON lists. The key names do not include ``[]``.

.. list-table:: Top-level config keys
   :header-rows: 1
   :widths: 22 16 12 50

   * - Key
     - JSON type
     - Required
     - Description and default
   * - ``office``
     - string
     - No
     - Informational CWMS office ID, such as ``MVP`` or ``MVM``. The runtime
       target comes from ``--office``.
   * - ``pi_namespace``
     - string
     - No
     - PI-XML namespace. Defaults to
       ``http://www.wldelft.nl/fews/PI``.
   * - ``location_alias_groups``
     - array of objects
     - Conditional
     - Location groups used to resolve NWS IDs to CWMS locations. Later groups
       override earlier groups. Needed for built TSIDs and derived group aliases.
   * - ``timeseries_group``
     - object
     - No
     - Time-series group used for alias-based TSID overrides. When omitted,
       resolution proceeds directly to the optional built fallback.
   * - ``build_missing_timeseries``
     - boolean
     - No
     - Enables building TSIDs not matched by ``timeseries_group``. Defaults to
       ``false``; unmatched series are otherwise skipped.
   * - ``parameter_rules``
     - array of objects
     - No
     - Location-sensitive CWMS parameter overrides applied before
       ``parameter_map``.
   * - ``parameter_suffix_rules``
     - array of objects
     - No
     - Optional suffixes applied after parameter resolution, such as
       ``-Non_contrib``.
   * - ``duplicate_preference_rules``
     - array of objects
     - No
     - Tie-breakers for series resolving to the same TSID. Higher ``priority``
       wins.
   * - ``parameter_map``
     - object
     - Conditional
     - NWS-to-CWMS parameter mapping used by the built fallback. Needed for
       parameters not covered by ``parameter_rules``.
   * - ``param_type_rules``
     - array of objects
     - No
     - Rules that set type and duration when a CWMS parameter contains a
       configured substring.
   * - ``default_type``
     - string
     - No
     - Fallback CWMS type. Defaults to ``Inst``.
   * - ``default_duration``
     - string
     - No
     - Fallback CWMS duration. Defaults to ``0``.
   * - ``runs``
     - array of objects
     - No
     - Run definitions matched top-to-bottom by filename. If supplied, end
       with ``{"match": {"default": true}}``.
   * - ``default_version_part``
     - string
     - No
     - Version part used by the implicit unversioned run when ``runs`` is
       omitted. Defaults to an empty string.
   * - ``issued_time``
     - object
     - No
     - Issued-time blob configuration. Issued-time tracking is disabled when
       omitted.
   * - ``watersheds``
     - object
     - No
     - NCRFC watershed keys mapped to labels and CWMS watersheds for
       issued-time tracking.

Run configuration
~~~~~~~~~~~~~~~~~

See ``runs`` in the downloadable
:download:`MVP example config <../nws/mvp.example.json>` for multiple
filename-matched runs and the
:download:`MVM example config <../nws/mvm.example.json>` for a single default
run.

Each run entry controls:

- ``match`` — how to match the run (``filename_contains`` or ``default``)
- ``version_part`` — the version segment of the TSID
- ``versioned`` — whether to write a versioned time series
- ``version_source`` — where to get the version date
  (``filename_timestamp``, ``creation_date``, or ``forecast_date``)
- ``version_fallback_source`` — optional source to use when
  ``version_source`` is unavailable
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
2. **Built fallback (optional)** — if ``build_missing_timeseries`` is true,
   construct
   ``{cwms_loc}.{param}.{type}.{interval}.{duration}.{version_part}`` from
   the mapped parameter, derived interval, and configured defaults.
   Unknown parameters, unresolved locations, and underivable intervals are
   warned and skipped.  If ``build_missing_timeseries`` is false or omitted,
   unmatched series are skipped instead of being built from the config. In a
   normal run, each unmatched series emits a warning identifying the series;
   under ``--dry-run``, the skip is included in ``skipped_by_reason`` as
   ``not_in_timeseries_group``.

If two series in one product resolve to the same TSID, only the first is
stored; the later one is dropped and reported as an error in the run summary
(and in the ``duplicates`` list under ``--dry-run``).  This usually means a
sub-location series fell back to its 5-character Handbook-5 prefix — add a
timeseries-group alias for it to disambiguate.

Under ``--dry-run``, the JSON report includes summary counts such as
``resolved_count``, ``skipped_by_reason``, and ``duplicate_count``.  Duplicate
entries keep compact ``kept``/``dropped`` source strings plus short
``kept_summary``/``ignored_summary`` fields so repeated
``locationId.parameterId`` headers can still be told apart without expanding
the report into nested per-series objects.

Time zones
~~~~~~~~~~

Event times in PI-XML carry no offset of their own; they are all expressed in
the document-level ``<timeZone>``, an offset from UTC in hours.  The loader
reads that element and converts every value to UTC before storing. For this
command, an absent ``<timeZone>`` is treated as UTC. An unparsable value also
falls back to UTC and emits a warning.

Version dates taken from the document (``creation_date``, ``forecast_date``)
are converted the same way.  A ``filename_timestamp`` is a naming convention
outside the document and is read as UTC.  ``version_snap_time`` is applied in
the source's own time zone — so it keeps naming the same calendar day — and
the result is stored as UTC.

MVP uses the trailing filename timestamp as its primary version source and
falls back to the PI-XML ``forecastDate``.  If the filename timestamp cannot
be parsed, the safely versioned data is still stored and the issued-time blob
slot is set to ``Date could not be parsed from filename``.  If neither the
primary nor fallback version source is available, the loader refuses to store
the versioned run.

Environment variables
---------------------

The following environment variables are recognized:

- ``OFFICE`` — default value for ``-o/--office``
- ``CDA_API_ROOT`` — default value for ``-a/--api-root``
- ``CDA_API_KEY`` — default value for ``-k/--api-key``

Example: MVP (St. Paul District) setup
--------------------------------------

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
