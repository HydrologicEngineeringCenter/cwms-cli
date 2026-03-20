Monthly Example
===============

This example shows a monthly SWT location report rendered with the text engine
and a ``text_layout`` template. The file includes a list of valid locations and
is meant to be run with ``--location`` for the specific lake you want.

Run it with:

.. code-block:: bash

   cwms-cli report generate ^
     --config cwmscli/reporting/examples/monthly_swt.yaml ^
     --location KEYS ^
     --month 2026-02 ^
     --out monthly_keys.txt

YAML
----

.. literalinclude:: ../../../cwmscli/reporting/examples/monthly_swt.yaml
   :language: yaml
   :caption: cwmscli/reporting/examples/monthly_swt.yaml
