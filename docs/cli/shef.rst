SHEF Configuration Imports
==========================

.. include:: ../_generated/maintainers/shef.inc

``cwms-cli shef`` imports legacy configuration into CWMS time-series groups.
It does not ingest SHEF observation messages. Install ``cwms-python`` and set
the office and CDA connection using :doc:`api_arguments`.

Import a .crit file
-------------------

``import_crit`` reads acquisition mappings and adds them to the
``SHEF Data Acquisition`` group in the ``Data Acquisition`` category.
The parser expects ``alias=timeseries-id;qualifiers`` mappings; it joins the
alias and qualifiers with ``:`` for the group's alias ID. Blank lines and
lines starting with ``#`` are ignored.

.. code-block:: bash

   cwms-cli shef import_crit --filename acquisition.crit --office SWT --dry-run

The preview lists parsed IDs and aliases without writing to CDA. With
``--dry-run`` removed, the command updates assignments without clearing the
existing members. The referenced time series and acquisition group must exist.

Import an exportShef .in file
----------------------------------------

``import_infile`` creates or updates the named group in the ``SHEF Export``
category by default. Use ``--category`` to select another category.

.. code-block:: bash

   cwms-cli shef import_infile --filename export.in --group-name "Daily Export" --office SWT --dry-run

A minimal configuration looks like:

.. code-block:: text

   LOCATION Example = ABCD1
   PE Stage = HG;units=ft
   Example.Stage.Inst.1Hour.0.Raw

The importer derives group aliases from the SHEF location, PE code, send code,
duration, and optional units. ``--dry-run`` prints the JSON payload. Review it
before rerunning without that flag: the update fallback replaces the group's
assigned time series. On a failed save, missing time-series IDs can be logged
and skipped before retrying with the remaining entries.

Both commands accept ``--api-key-loc`` to read a key from the first line of a
file. See :doc:`../cli` for the complete command options.
