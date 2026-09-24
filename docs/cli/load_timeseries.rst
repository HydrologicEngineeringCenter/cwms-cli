Load Time Series
================

.. include:: ../_generated/maintainers/load_timeseries.inc

Use ``cwms-cli load timeseries`` to copy identifiers or values between CDA
instances. Install ``cwms-python`` as described in :doc:`setup` and
:doc:`load locations <load_location_ids_all>` into the target first.

These commands retain the source office; they do not remap data to the office
stored in a target named environment. Supply ``--source-office`` (or set it in
``--source-env``). There is no ``--target-office`` option for these commands.

Copy identifiers
----------------

``ids-all`` stores time-series metadata, not observations. Limit the source
catalog with ``--timeseries-id-regex`` using :doc:`CDA regex syntax <cda_regex>`:

.. code-block:: bash

   cwms-cli load timeseries ids-all --source-office SPK --target-cda http://localhost:8082/cwms-data/ --timeseries-id-regex '^Black Butte\.' --dry-run

Review the preview, then remove ``--dry-run`` to store the identifiers.
Existing identifiers are allowed (``fail_if_exists=False``).

Copy values
-----------

Choose exactly one of ``--ts-id`` or ``--ts-group``. A ``--ts-id`` value can
contain multiple IDs separated by commas or newlines. Use explicit timestamps
with UTC offsets for a repeatable window; the default window is the previous
day through the time the command starts.

.. code-block:: bash

   cwms-cli load timeseries data --source-office SPK --target-cda http://localhost:8082/cwms-data/ --ts-id "Black Butte.Flow.Inst.1Hour.0.raw-cda" --begin 2026-01-01T00:00:00+00:00 --end 2026-01-02T00:00:00+00:00 --dry-run

Select group members instead with ``--ts-group "My Group"``. Use
``--ts-group-category-id`` and ``--ts-group-category-office-id`` to narrow the
group search. The command combines matching groups, removes duplicate IDs,
and copies only members belonging to the source office. It does not copy the
group definitions.

Value writes use ``REPLACE_ALL`` without overriding protection. Null values
are omitted. Review the selected IDs and window before removing ``--dry-run``.

Connections and previews
------------------------

- The source defaults to public CDA; the target defaults to
  ``http://localhost:8081/cwms-data/``. Set the target explicitly for your instance.
- Use ``--target-api-key`` or ``CDA_API_KEY`` for target credentials.
  :doc:`Named environments <env>` provide ``--source-env`` and ``--target-env``
  alternatives to URLs; an environment and its corresponding explicit URL
  cannot be supplied together.
- A dry run still reads source data and checks that the target is a CDA
  service. It suppresses writes, not network access.
- ``--skip-target-cda-check`` skips only the target preflight probe. It does
  not make a transfer offline or validate credentials.

See :doc:`../cli` for all options and :doc:`troubleshooting` for connection errors.
