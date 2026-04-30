Load Locations
==============

.. include:: ../_generated/maintainers/load_location_ids_all.inc

Use ``cwms-cli load location ids-all`` to copy locations selected by the
source CDA catalog into a target CDA. Use
``cwms-cli load location ids-bygroup`` to copy the locations that belong to a
source CDA location group.

Both commands can write selected locations to CSV files instead of storing them
to a target CDA. The ``ids-all`` command can also read locations back from a
CSV file and store them to a target CDA.

The ``ids-all`` command passes ``--like`` and ``--location-kind-like`` directly
to the source CDA catalog, so both options use CDA regular expression behavior.
The CLI does not apply extra exact-match filtering. For CDA regex syntax, see
the :doc:`CWMS Data API regular expression guide <cda_regex>`.

CDA to CDA Examples
-------------------

Exact location name:

.. code-block:: shell

   cwms-cli load location ids-all \
     --source-cda "https://cwms-data.usace.army.mil/cwms-data/" \
     --source-office SPK \
     --target-cda "http://localhost:8082/cwms-data/" \
     --target-api-key "apikey 0123456789abcdef0123456789abcdef" \
     --like "^Black Butte$" \
     --location-kind-like PROJECT

Prefix match:

.. code-block:: shell

   cwms-cli load location ids-all \
     --source-office SPK \
     --target-cda "http://localhost:8082/cwms-data/" \
     --like "^Black Butte.*"

Match multiple kinds:

.. code-block:: shell

   cwms-cli load location ids-all \
     --source-office SPK \
     --target-cda "http://localhost:8082/cwms-data/" \
     --like ".*Butte.*" \
     --location-kind-like "(PROJECT|STREAM)"

Copy locations from a location group:

.. code-block:: shell

   cwms-cli load location ids-bygroup \
     --source-cda "https://cwms-data.usace.army.mil/cwms-data/" \
     --source-office SPK \
     --target-cda "http://localhost:8082/cwms-data/" \
     --target-api-key "apikey 0123456789abcdef0123456789abcdef" \
     --group-id "Sacramento River" \
     --category-id Basin \
     --group-office-id SPK \
     --category-office-id SPK

CSV Files
---------

Use ``--target-csv`` when you want to save matching locations to a CSV file
instead of writing them to a target CDA. Use ``--source-csv`` with
``ids-all`` when you want to load locations from a previously exported CSV
file.

``--target-csv`` is mutually exclusive with ``--target-cda``. ``--source-csv``
is mutually exclusive with ``--source-cda``. If both the source and target are
CSV files, use a normal file copy instead of ``cwms-cli``.

Export locations selected by the CDA catalog:

.. code-block:: shell

   cwms-cli load location ids-all \
     --source-cda "https://cwms-data.usace.army.mil/cwms-data/" \
     --source-office SPK \
     --like "^Black Butte$" \
     --location-kind-like PROJECT \
     --target-csv "black-butte-location.csv"

Export all resolved members of a location group:

.. code-block:: shell

   cwms-cli load location ids-bygroup \
     --source-cda "https://cwms-data.usace.army.mil/cwms-data/" \
     --source-office SPK \
     --group-id "Sacramento River" \
     --category-id Basin \
     --group-office-id SPK \
     --category-office-id SPK \
     --target-csv "sacramento-river-locations.csv"

Load locations from a CSV file into a target CDA:

.. code-block:: shell

   cwms-cli load location ids-all \
     --source-csv "black-butte-location.csv" \
     --target-cda "http://localhost:8082/cwms-data/" \
     --target-api-key "apikey 0123456789abcdef0123456789abcdef"

Preview a CSV load without storing records:

.. code-block:: shell

   cwms-cli load location ids-all \
     --source-csv "black-butte-location.csv" \
     --target-cda "http://localhost:8082/cwms-data/" \
     --dry-run

CSV Output
----------

CSV exports include the location fields returned by CDA, with no added index
column. A small export looks like this:

.. code-block:: text

   office-id,name,latitude,longitude,active,public-name,location-kind,elevation-units
   SPK,Black Butte,39.8006222,-122.3581694,True,Black Butte Lake,PROJECT,ft

Notes
-----

- Use ``^...$`` when you want an exact location name.
- Use ``.*`` for wildcard-style matching.
- Quote regex values in the shell so characters such as ``^``, ``$``, and ``|`` are preserved.
- Use the :doc:`CWMS Data API regular expression guide <cda_regex>` when you need CDA-specific regex examples or syntax details.
- Use ``--filter-office`` with ``ids-bygroup`` to keep only group members whose ``office-id`` matches ``--source-office``. This is the default.
