Reporting Overview
==================

Report generation is built around one command:

.. code-block:: bash

   cwms-cli report generate --config path/to/report.yaml

The command loads the YAML configuration, builds a report context from CWMS
data, renders the selected output, and writes the final file to disk.

Typical workflow
----------------

1. Choose a dataset shape.
2. Choose a rendering engine.
3. Define the report metadata and output template.
4. Run ``cwms-cli report generate`` with the config file.

Important concepts
------------------

``dataset.kind``
   Controls how data is assembled before rendering. The current reporting code
   supports the standard table dataset plus monthly and yearly single-location
   report paths.

``engine.name``
   Selects the output renderer. Built-in engines are ``text`` and ``jinja2``.

``template.kind``
   Controls how template options are interpreted. The default table renderer can
   work without a template block, while monthly text reports typically use
   ``text_layout``.

``projects`` and ``columns``
   Used by table-style reports. Projects define rows, and columns define
   timeseries or levels to retrieve for each project.

``dataset.series`` and ``dataset.levels``
   Used by monthly reports. These define the raw source data that is assembled
   into daily rows, summary fields, and derived values.

CLI options
-----------

The reporting command supports a few useful runtime overrides:

* ``--config`` points to the YAML file.
* ``--location`` overrides the configured location or project for monthly runs.
* ``--month`` overrides the configured monthly period.
* ``--engine`` switches between ``text`` and ``jinja2`` without changing the
  file.
* ``--template-dir`` and ``--template`` let you supply custom Jinja templates.
* ``--out`` controls the output path.

See also
--------

* :doc:`configuration`
* :doc:`engines`
* :doc:`templates`
* :doc:`examples/index`
