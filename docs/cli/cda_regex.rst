CDA Regex Guide
===============

Several ``cwms-cli`` subcommands pass regex filters directly to CWMS Data API
endpoints. Common examples include:

- ``cwms-cli load location ids-all --like ...``
- ``cwms-cli load location ids-all --location-kind-like ...``
- ``cwms-cli load timeseries ids-all --timeseries-id-regex ...``

These options use CDA endpoint regex semantics. ``cwms-cli`` does not convert
shell wildcards such as ``*`` into regex for you.

Examples
--------

Exact match:

.. code-block:: text

   ^Black Butte$

Prefix match:

.. code-block:: text

   ^Black Butte.*

Contains match:

.. code-block:: text

   .*Butte.*

Regex OR:

.. code-block:: text

   (PROJECT|STREAM)

Notes
-----

- Use ``^`` and ``$`` when you want an exact match.
- Use ``.*`` for wildcard-style matching.
- Quote regex values in the shell so characters such as ``^``, ``$``, ``|``,
  and ``()`` are passed through unchanged.
- When a command fetches one exact returned ID, it escapes that ID before
  building a follow-up regex so literal characters stay literal.

See also
--------

- :doc:`Common API Arguments <api_arguments>`
- :doc:`load location ids-all <load_location_ids_all>`

For more reading
----------------

- CWMS Data API regex page: https://cwms-data.usace.army.mil/cwms-data/regexp
