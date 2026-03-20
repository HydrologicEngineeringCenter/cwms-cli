Reporting
=========

The reporting commands let you generate reservoir reports from declarative YAML
files. A report definition describes:

* where to fetch CWMS data
* what dataset shape to build
* how to render the output

The main entrypoint is:

.. code-block:: bash

   cwms-cli report generate --config path/to/report.yaml

.. toctree::
   :maxdepth: 2

   overview
   configuration
   engines
   templates
   examples/index
