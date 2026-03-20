Configuration Reference
=======================

Top-level structure
-------------------

Most report files use a subset of the following top-level keys:

.. code-block:: yaml

   office: "SWT"
   cda_api_root: "https://cwms-data.usace.army.mil/cwms-data/"
   time_zone: "America/Chicago"
   default_unit: "EN"

   engine:
     name: "text"

   report:
     district: "Tulsa District SWT"
     name: "Example Report"

Dataset kinds
-------------

``table``
   The default dataset kind. This is used for row-and-column reports where each
   configured project becomes a row and each configured column resolves either a
   timeseries or a level.

``monthly_location`` and ``monthly_project``
   Monthly report builders that assemble daily rows, summaries, extremes, level
   values, and derived fields for a single selected location/project and month.

``yearly_location`` and ``yearly_project``
   Yearly report builders that assemble one row per month for a single selected
   location/project and year. These reports are designed for Jan-Dec summaries
   built from 1Month series plus monthly statistics computed from higher
   frequency source data.

Table report fields
-------------------

Table reports commonly use these sections:

``begin`` and ``end``
   The sampling window for the table. Each column resolves the last value found
   in its effective time window.

``projects``
   List of location IDs to use as report rows.

``columns``
   Per-column retrieval and formatting rules.

Column fields
-------------

The most important column keys are:

``title``
   Display label in the rendered output.

``key``
   Internal identifier used in the report context.

``tsid`` or ``level``
   Data source for the column. A column must declare exactly one of these.

``unit`` and ``precision``
   Controls the requested units and rendered numeric precision.

``begin`` and ``end``
   Optional per-column time window overrides.

``href``
   Optional URL template included in HTML output.

Monthly report fields
---------------------

Monthly reports use a different layout under ``dataset``:

``locations`` or ``projects``
   Allowed location IDs for the report.

``month``
   Monthly period in ``YYYY-MM`` format.

``series``
   Source timeseries definitions. Each entry can specify a TSID, time anchors,
   report hour filtering, precision, and mode.

``levels``
   Source location level definitions used for things like pool limits and
   normals.

``derived``
   Calculated fields built from source series, row values, summaries, and
   previously defined derived values.

Yearly report fields
--------------------

Yearly reports use a Jan-Dec monthly row model:

``location`` or ``project``
   The selected location for the annual report.

``year``
   Four-digit year for the report window.

``monthly_series``
   Published 1Month series that contribute one value per month.

``hourly_series``
   Higher-frequency source series used to compute monthly ``avg``, ``min``, and
   ``max`` values.

Anchors and time parsing
------------------------

Table reports use the flexible date parser in ``cwmscli.reporting.utils.date``.
It accepts ISO timestamps, ``strftime`` placeholders, and simple natural-language
expressions such as ``yesterday 0800``.

Monthly reports use named anchors such as:

* ``month_start_midnight``
* ``month_start_report``
* ``month_end_report``
* ``month_end_report_plus_one``
* ``month_start_report_yesterday``

End-user guidance
-----------------

Start with a working example and then change one concern at a time:

* update the office and CDA root if needed
* verify the TSIDs and level IDs first
* keep units explicit on each field
* use ``--location`` and ``--month`` for monthly reruns instead of editing the
  file each time
