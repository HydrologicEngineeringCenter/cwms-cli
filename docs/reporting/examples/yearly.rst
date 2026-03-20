Yearly Example
==============

This example shows an example Jan-Dec yearly SWT report for ``Keystone Lake`` using the
``yearly_location`` dataset. It combines published 1Month flow-volume series
with monthly end-of-month, average, minimum, and maximum elevation values
computed from the hourly elevation record.

This report uses KEYS monthly series such as:

* ``KEYS.Volume-Res In.Total.~1Month.1Month.Ccp-Rev``
* ``KEYS.Volume-Res Out.Total.~1Month.1Month.Ccp-Rev``

The example uses the monthly inflow and outflow volume series directly and then
computes monthly ``last``, ``avg``, ``min``, and ``max`` values from
``KEYS.Elev.Inst.1Hour.0.Ccp-Rev``.

Run it with:

.. code-block:: bash

   cwms-cli report generate ^
     --config cwmscli/reporting/examples/yearly_swt.yaml ^
     --out yearly_keys.txt

YAML
----

.. literalinclude:: ../../../cwmscli/reporting/examples/yearly_swt.yaml
   :language: yaml
   :caption: cwmscli/reporting/examples/yearly_swt.yaml
