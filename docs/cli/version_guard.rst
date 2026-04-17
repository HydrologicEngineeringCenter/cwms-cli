Version Guard Decorator
=======================

``cwms-cli`` uses a ``@requires`` decorator to ensure optional Python
dependencies are installed before a command runs. This page explains how
contributors can use it when adding new commands.

Overview
--------

The ``requires`` decorator lives in ``cwmscli/utils/deps.py``. Apply it to
any Click command that depends on packages that are not part of the core
``cwms-cli`` install.

When a user runs a command that has unmet dependencies, ``cwms-cli`` will
print a clear error message listing the missing packages and the exact
``pip`` command needed to install them.

Usage
-----

Import ``requires`` and the shared requirements registry:

.. code-block:: python

   from cwmscli.utils.deps import requires
   from cwmscli import requirements as reqs

Then decorate your command:

.. code-block:: python

   @some_group.command("my-command", help="Does something useful")
   @requires(reqs.cwms, reqs.requests)
   def my_command():
       ...

Requirement dictionary keys
---------------------------

Each entry passed to ``@requires`` is a dictionary with the following keys:

.. list-table::
   :header-rows: 1
   :widths: 20 10 70

   * - Key
     - Required
     - Description
   * - ``module``
     - Yes
     - The importable Python module name (e.g. ``"requests"``).
   * - ``package``
     - No
     - The pip install name when it differs from the module name
       (e.g. ``"cwms-python"`` for ``import cwms``).
   * - ``version``
     - No
     - Minimum required version string (e.g. ``"2.30.0"``).
   * - ``desc``
     - No
     - Short description included in the error message.
   * - ``link``
     - No
     - URL to documentation or the package homepage.

Example with all keys
---------------------

.. code-block:: python

   @requires(
       {
           "module": "cwms",
           "package": "cwms-python",
           "version": "1.0.7",
           "desc": "CWMS REST API Python client",
           "link": "https://github.com/hydrologicengineeringcenter/cwms-python"
       },
       {
           "module": "requests",
           "version": "2.30.0",
           "desc": "Required for HTTP API access"
       }
   )
   def my_command():
       ...

Pre-defined requirements
------------------------

Common requirements are pre-defined in ``cwmscli/requirements.py`` and can be
referenced directly:

.. code-block:: python

   @requires(reqs.cwms, reqs.requests, reqs.dataretrieval)

See also
--------

- :doc:`CLI reference <../cli>`
- :doc:`Common API arguments <api_arguments>`
