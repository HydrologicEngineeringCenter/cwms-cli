Load Location ids-all
=====================

Use ``cwms-cli load location ids-all`` to copy locations selected by the
source CDA catalog into a target CDA.

This subcommand passes ``--like`` and ``--location-kind-like`` directly to the
source CDA catalog, so both options use CDA regular expression behavior. The
CLI does not apply extra exact-match filtering. For CDA regex syntax, see the
|cda-regexp-guide|_.

Examples
--------

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

Notes
-----

- Use ``^...$`` when you want an exact location name.
- Use ``.*`` for wildcard-style matching.
- Quote regex values in the shell so characters such as ``^``, ``$``, and ``|`` are preserved.
- Use the |cda-regexp-guide|_ when you need CDA-specific regex examples or syntax details.
