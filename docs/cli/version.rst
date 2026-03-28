Version argument
================

Use the version argument to print the installed ``cwms-cli`` version and exit.
If a newer release is available on PyPI, ``cwms-cli`` also prints a short
upgrade hint that points to ``cwms-cli update``.

Examples
--------

- Long form:

  ``cwms-cli --version``

- Short form:

  ``cwms-cli -V``

See also
--------

- :doc:`Update command <update>`

The ``update`` command can upgrade the installed package, and then you can run
``cwms-cli --version`` to verify the result. It also supports
``--target-version`` when you need to install an exact release.
