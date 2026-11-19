USGS workflows
==============

The ``usgs`` command group retrieves USGS data and stores it in CWMS through
the CWMS Data API (CDA). It includes continuous time-series values, ratings,
and migration support for installations moving from legacy USGS method IDs to
the USGS Water Data API.

Prerequisites and authentication
---------------------------------

Install the optional dependencies used by USGS commands:

.. code-block:: bash

   pip install cwms-python dataretrieval

USGS commands use the shared CDA options documented in
:doc:`Common API Arguments <api_arguments>`:

* ``--office`` / ``OFFICE``
* ``--api-root`` / ``CDA_API_ROOT``
* ``--api-key`` / ``CDA_API_KEY``
* ``--api-key-loc``

The Water Data API key is optional. Provide it with ``--usgs-api-key`` or the
``USGS_API_KEY`` environment variable. When neither is provided,
``dataretrieval`` can use its configured ``API_USGS_PAT`` environment value.
The CLI warns when no USGS key is supplied.

Configure CWMS group assignments
--------------------------------

Before retrieving values, configure these groups in CWMS for the target
office:

1. In **Agency Aliases / USGS Station Number**, assign the USGS site number to
   the CWMS location. Enter the station number, such as ``05389500``, as the
   location's ``alias-id``; do not include the ``USGS-`` prefix. The CLI uses
   this alias to form the USGS monitoring location ID. If a time series uses a
   sublocation without its own station alias, the CLI can use the alias on its
   base location.
2. In **Data Acquisition / USGS TS Data Acquisition**, assign the CWMS time
   series that should be populated by USGS data.
3. Set the group's ``attribute`` to a USGS parameter code when the default
   mapping for the CWMS parameter is not the one you need. The current default
   mappings include:

   +----------------+------------------+
   | CWMS parameter | USGS code        |
   +================+==================+
   | Temp-Water     | 00010            |
   +----------------+------------------+
   | Temp-Air       | 00021            |
   +----------------+------------------+
   | Speed-Wind     | 00035            |
   +----------------+------------------+
   | Dir-Wind       | 00036            |
   +----------------+------------------+
   | Precip-Inc     | 00045            |
   +----------------+------------------+
   | Precip         | 00045            |
   +----------------+------------------+
   | %-Humidity     | 00052            |
   +----------------+------------------+
   | Flow           | 00060            |
   +----------------+------------------+
   | Stage          | 00065            |
   +----------------+------------------+
   | Cond           | 00095            |
   +----------------+------------------+
   | Conc-Salinity  | 00096            |
   +----------------+------------------+
   | Stor           | 72036            |
   +----------------+------------------+
   | Irrad-Solar    | 62608            |
   +----------------+------------------+
   | Elev           | 63160            |
   +----------------+------------------+

   Leave the attribute blank or set it to ``0`` to use the default mapping.
   Enter the five-digit USGS code to override it.
4. If the station and parameter identify more than one USGS time series, set
   the time-series group's ``alias-id`` to the specific USGS ``id`` found in
   :ref:`Finding a USGS time_series_id <finding-usgs-timeseries-id>`. Leave
   it blank when a station-and-parameter query identifies the desired series
   without ambiguity. Do not enter a legacy numeric method ID; use
   :ref:`the migration workflow <migrate-usgs-timeseries-ids>` for those
   configurations.

Save the group changes in CWMS before running ``cwms-cli usgs timeseries``.

Continuous values
-----------------

Retrieve USGS continuous values with:

.. code-block:: bash

   cwms-cli usgs timeseries \
     --office SWT \
     --api-root https://cwms-data.usace.army.mil/cwms-data \
     --api-key "$CDA_API_KEY" \
     --days-back 1 \
     --usgs-api-key "$USGS_API_KEY"

The ``USGS TS Data Acquisition`` group controls how each CWMS time series is
queried:

* A blank ``alias-id`` queries by USGS station number and parameter code.
* A non-numeric USGS ``time_series_id`` in ``alias-id`` queries that series
  directly.
* Numeric legacy method IDs are not interpreted as new IDs. They are skipped
  and must be migrated first; see :ref:`migrate-usgs-timeseries-ids`.

``--days-back`` selects observations modified during the lookback window. By
default, observations are also limited to that same period. Use
``--revision-lookback-days`` to retrieve older observations that were revised
within the day back window.  For exmaple, ``--days-back 1 --revision-lookback-days 7`` 
retrieves observations modified in the last day, including any revisions to observations 
from the last week.  By default -revision-lookback-days is set to --day-back mimicking 
the behavior of previous versions.  

Use ``--backfill`` with a comma-separated list of CWMS time-series IDs to
process only selected series. Use ``--backfill-version`` to write to another
existing version, such as ``Rev-USGS`` instead of ``Raw-USGS``. The command
checks that the requested version exists and skips source series without a
matching destination.

Finding a USGS ``time_series_id``
---------------------------------

.. _finding-usgs-timeseries-id:

You can find the identifier in the USGS Water Data website without making an
API request manually:

1. Open the USGS `Download data form
   <https://api.waterdata.usgs.gov/download>`_.
2. Enter the monitoring location ID. The form accepts IDs such as
   ``USGS-05389500``. You can also select a state or county.
3. Enter the five-digit parameter code, such as ``00065`` for gage height.
4. Select **Time series metadata**, then click **Download data**.

Open the downloaded CSV to see the time series available for that site and
parameter. Use the ``web_description`` field to help identify the correct time
series for your CWMS record. The value to enter in the CWMS ``USGS TS Data
Acquisition`` group's ``alias-id`` field is the ``id`` value in the first
column of the CSV.

For example, enter ``USGS-05389500`` as the monitoring location ID, select the
desired parameter, and inspect the downloaded metadata rows. Choose the row
whose ``web_description`` matches the time series you need, then copy its
first-column ``id`` into ``alias-id``. After updating the alias, use
``cwms-cli usgs timeseries`` to retrieve data for the configured CWMS time
series.

.. _migrate-usgs-timeseries-ids:

Migrate legacy time-series IDs
------------------------------

Older configurations may store numeric USGS WaterServices ``methodID`` values
in the ``alias-id`` field. The new continuous-value workflow requires USGS
Water Data API ``time_series_id`` values or blank aliases. The migration
command builds a crosswalk and is dry-run by default:

Full-office dry run
^^^^^^^^^^^^^^^^^^^

Omit ``--timeseries-ids`` to process every time series in the selected
office's ``Data Acquisition / USGS TS Data Acquisition`` group that has a
numeric legacy method ID in ``alias-id``. Other group assignments are not
migration candidates.

Set the CDA API key and run a full-office dry run:

.. code-block:: batch

   set "CWMS_API_KEY=your-CDA-api-key"

   cwms-cli usgs migrate-timeseries-ids ^
     --office LRL ^
     --api-root "https://your-cda-host/cwms-data" ^
     --api-key "%CWMS_API_KEY%" ^
     --output-dir ".\usgs_tsid_full_dryrun" ^
     --compare-timeseries ^
     --dry-run

``--dry-run`` is the default, but is included to make it explicit. No CWMS
assignments are changed during a dry run. The value-comparison defaults are a
three-day window, a ``0.001`` absolute tolerance, at least 20 overlapping
observations, and at least 95 percent agreement. Adjust these with
``--compare-days``, ``--comparison-tolerance``,
``--comparison-min-records``, and ``--comparison-min-agreement``.

How the migration evaluates candidates
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The command reads the office's USGS acquisition group and uses its location
alias and parameter ``attribute`` (or the default parameter mapping) to look
up new USGS metadata. It retrieves legacy method descriptions from the old
WaterServices API unless ``--legacy-methods-csv`` is supplied. That CSV must
contain ``USGS_St_Num``, ``USGS_PARAMETER``, ``methodID``, and
``methodDescription`` columns.

The migration compares each legacy method description with one reconstructed
from the new metadata, including ``sublocation_identifier`` and
``web_description``. With ``--compare-timeseries``, it also compares
candidate observations to CWMS values after unit normalization. If exactly
one candidate agrees with CWMS, the migration can select its new
``time_series_id``.

The command also checks whether a direct station-and-parameter query is
unambiguous and agrees with CWMS. When that check succeeds, the recommended
update is a blank ``alias-id`` rather than a UUID. If the intended series
cannot be identified safely, the existing ``alias-id`` is left unchanged.

Review the reports
^^^^^^^^^^^^^^^^^^

Review the CSV files in the output directory before applying changes. Report
names include the office and a timestamp:

* ``methodid_to_timeseriesid_crosswalk_<office>_<timestamp>.csv`` is the main
  audit report. Review ``timeseries-id``, ``legacy_method_id``,
  ``time_series_id``, ``metadata_mapping_status``, ``mapping_status``,
  ``comparison_status``, ``agreement_percent``, and
  ``unaliased_comparison_status``.
* ``cwms_alias_update_plan_<office>_<timestamp>.csv`` contains only mappings
  eligible for update. ``matched`` and ``matched_by_value_comparison`` rows
  propose a new USGS ID in ``new_alias_id``.
  ``matched_without_alias_by_value_comparison`` proposes a blank
  ``new_alias_id``; this is sent to CWMS as ``"alias-id": null``.
* When the update plan is nonempty,
  ``cwms_alias_patch_<office>_<timestamp>.csv`` contains the exact group
  records to be sent to CWMS. Confirm ``timeseries-id``, ``alias-id``, and
  ``attribute``; the existing ``attribute`` is preserved.
* With ``--compare-timeseries``, the command also writes
  ``cwms_usgs_value_comparison_<office>_<timestamp>.csv`` and
  ``cwms_usgs_unaliased_comparison_<office>_<timestamp>.csv``.
  ``cwms_usgs_value_mismatches_<office>_<timestamp>.csv`` contains aligned
  observations for candidates whose new-USGS values did not agree with CWMS;
  legacy WaterServices values are included where available.

The command also writes ``legacy_methods_*.csv``,
``new_usgs_metadata_*.csv``, and ``migration_summary_*.csv`` reports. Keep
the dry-run reports as the migration audit record.

Apply approved updates
^^^^^^^^^^^^^^^^^^^^^^

After reviewing the dry-run reports, rerun with a separate output directory
and ``--apply``:

.. code-block:: batch

   cwms-cli usgs migrate-timeseries-ids ^
     --office LRL ^
     --api-root "https://your-cda-host/cwms-data" ^
     --api-key "%CWMS_API_KEY%" ^
     --output-dir ".\usgs_tsid_apply" ^
     --compare-timeseries ^
     --apply

The command updates only eligible assignments in
``Data Acquisition / USGS TS Data Acquisition``. It changes ``alias-id`` and
preserves the time-series group's ``attribute``. After applying, verify the
group values: a selected UUID is stored in ``alias-id``; a safe
station-and-parameter query leaves ``alias-id`` blank; and any mapping without
a safe match retains its previous value. Keep both dry-run and apply reports
for auditing.




Ratings
-------

Rating specification setup
^^^^^^^^^^^^^^^^^^^^^^^^^^

The ratings command uses CWMS rating specifications for the requested office.
Each specification's location must have a USGS station number in the
**Agency Aliases / USGS Station Number** group described above. Configure the
rating specification in CWMS-Vue with:

* **Source Agency** set to ``USGS``.
* **Active** and **Auto Update** enabled.
* A description containing one rating type marker:
  ``USGS-EXSA`` (extrapolated), ``USGS-CORR`` (corrected), or ``USGS-BASE``
  (base). The marker determines which USGS rating the command retrieves.

The current command selects specifications that are active, have Auto Update
enabled, and contain one of these markers in the description. The following
CWMS-Vue screenshot illustrates the rating specification settings. Image
from the HEC USGS ratings guide.

.. figure:: ../_static/usgs-ratings/rating-specification-settings.png
   :alt: Example CWMS rating specification settings for the USGS ratings command
   :width: 90%

The **Auto Activate** flag controls whether a newly stored rating is active.
Disable it if new USGS ratings should be stored inactive. Image from the
HEC USGS ratings guide.

.. figure:: ../_static/usgs-ratings/rating-curve-active.png
   :alt: Example of an active CWMS rating curve
   :width: 90%

When **Auto Migrate** is enabled, extensions on the existing rating
are migrated to the newly stored rating. This option applies when a rating
already exists. Image from the HEC USGS ratings guide.

.. figure:: ../_static/usgs-ratings/rating-extension-example.png
   :alt: Example of a CWMS rating extension
   :width: 90%

Run the ratings command
^^^^^^^^^^^^^^^^^^^^^^^

Retrieve updated USGS ratings with:

.. code-block:: bash

   cwms-cli usgs ratings \
     --office SWT \
     --api-root https://cwms-data.usace.army.mil/cwms-data \
     --api-key "$CDA_API_KEY" \
     --days-back 1 \
     --usgs-api-key "$USGS_API_KEY"

By default, existing rating specifications are selected when their USGS
rating asset was updated during ``--days-back``. New specifications without an
existing CWMS curve are included when their asset is updated. Use
``--rating-subset`` with comma-separated rating specification IDs to retrieve
the current rating for selected specifications regardless of the update
window. A rating is not stored again when its USGS effective date already
matches the most recent effective date in CWMS.

``--days-back`` is the USGS rating-asset update lookback. For example,
``--days-back 2`` checks rating assets updated in the last two days; it does
not mean that rating curves older than two days are discarded.

Use ``--dry-run`` to retrieve and validate ratings without writing them to
CWMS:

.. code-block:: bash

   cwms-cli usgs ratings --office SWT --rating-subset "rating-id-1" --dry-run

Rating-spec imports
-------------------

Use ``ratings-ini-file-import`` to update rating specifications listed in a
legacy ratings INI file:

.. code-block:: bash

   cwms-cli usgs ratings-ini-file-import \
     --filename ratings.ini \
     --api-root "$CDA_API_ROOT" \
     --api-key "$CDA_API_KEY" \
     --dry-run

For recognized ``store_exsa``, ``store_corr``,
``store_base``, or ``replace_exsa`` entries, it sets Source Agency to ``USGS``,
enables Active, Auto Update, and Auto Activate, and adds the matching
``USGS-EXSA``, ``USGS-CORR``, or ``USGS-BASE`` description marker. Use
``--dry-run`` to preview proposed changes. Remove ``--dry-run`` to apply them.

The image below shows an example of the INI file format from the HEC USGS
ratings guide.

.. figure:: ../_static/usgs-ratings/ratings-ini-example.png
   :alt: Example legacy USGS ratings INI file
   :width: 90%

See ``cwms-cli usgs <command> --help`` for the complete options for each
command.
Python support
--------------

This release supports Python 3.10 and newer within the tested range. CI tests
Python 3.10 and 3.13, and the development container tests Python 3.12.