csv2cwms Supported Interval Identifiers
=======================================

When ``csv2cwms`` needs to parse the interval from a CWMS time series
identifier, it expects the interval part of the TSID to match one of the
supported interval identifiers below.

These values were directly pulled from the CWMS Data API database schema 
here: `<https://github.com/HydrologicEngineeringCenter/cwms-database>`_


These values come from the source list in
``cwmscli/utils/intervals.py``.

Regular intervals
-----------------

These interval identifiers can be used for ``round_to_nearest`` fallback and
can be converted into a fixed interval for rounding behavior.

.. list-table::
   :header-rows: 1
   :widths: 100

   * - Identifier
   * - ``1Minute``
   * - ``2Minutes``
   * - ``3Minutes``
   * - ``4Minutes``
   * - ``5Minutes``
   * - ``6Minutes``
   * - ``8Minutes``
   * - ``10Minutes``
   * - ``12Minutes``
   * - ``15Minutes``
   * - ``20Minutes``
   * - ``30Minutes``
   * - ``1Hour``
   * - ``2Hours``
   * - ``3Hours``
   * - ``4Hours``
   * - ``6Hours``
   * - ``8Hours``
   * - ``12Hours``
   * - ``1Day``
   * - ``2Days``
   * - ``3Days``
   * - ``4Days``
   * - ``5Days``
   * - ``6Days``
   * - ``1Week``
   * - ``1Month``
   * - ``1Year``
   * - ``1Decade``

Irregular intervals
-------------------

These identifiers are recognized by the parser, but irregular intervals are not
valid for ``round_to_nearest``.

.. list-table::
   :header-rows: 1
   :widths: 100

   * - Identifier
   * - ``0``
   * - ``~1Minute``
   * - ``~2Minutes``
   * - ``~3Minutes``
   * - ``~4Minutes``
   * - ``~5Minutes``
   * - ``~6Minutes``
   * - ``~8Minutes``
   * - ``~10Minutes``
   * - ``~12Minutes``
   * - ``~15Minutes``
   * - ``~20Minutes``
   * - ``~30Minutes``
   * - ``~1Hour``
   * - ``~2Hours``
   * - ``~3Hours``
   * - ``~4Hours``
   * - ``~6Hours``
   * - ``~8Hours``
   * - ``~12Hours``
   * - ``~1Day``
   * - ``~2Days``
   * - ``~3Days``
   * - ``~4Days``
   * - ``~5Days``
   * - ``~6Days``
   * - ``~1Week``
   * - ``~1Month``
   * - ``~1Year``
   * - ``~1Decade``

See also
--------

- :doc:`csv2cwms <csv2cwms>`
- :doc:`Complete config example <csv2cwms_complete_config>`
