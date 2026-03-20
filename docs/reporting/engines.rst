Report Engines
==============

The reporting system currently includes two built-in engines.

``text``
--------

The text engine renders plain-text output. It supports:

* the default table layout for standard table reports
* ``text_layout`` templates for more structured text reports

Typical configuration:

.. code-block:: yaml

   engine:
     name: "text"

The text engine is a good fit for console-friendly reports, plain-text email
content, and legacy operational report layouts.

``jinja2``
----------

The Jinja2 engine renders HTML from a template. It can use the built-in package
templates or a custom template directory supplied in the config or on the CLI.

Typical configuration:

.. code-block:: yaml

   engine:
     name: "jinja2"
     template: "report.html.j2"

Useful runtime overrides:

.. code-block:: bash

   cwms-cli report generate --config my_report.yaml --engine jinja2
   cwms-cli report generate --config my_report.yaml --template-dir ./templates
   cwms-cli report generate --config my_report.yaml --template custom.html.j2

How engine selection works
--------------------------

``engine.name`` in the YAML is the default.

``--engine`` on the CLI overrides the YAML value for a single run.

The selected engine determines the default output extension:

* ``text`` writes ``.txt``
* ``jinja2`` writes ``.html``
