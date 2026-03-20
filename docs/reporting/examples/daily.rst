Daily Example
=============

This example shows a daily SWT reservoir table rendered with the built-in Jinja2
HTML template.

Run it with:

.. code-block:: bash

   cwms-cli report generate ^
     --config cwmscli/reporting/examples/daily_swt.yaml ^
     --out daily_swt.html

YAML
----

.. literalinclude:: ../../../cwmscli/reporting/examples/daily_swt.yaml
   :language: yaml
   :caption: cwmscli/reporting/examples/daily_swt.yaml
