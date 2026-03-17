Common API Arguments
====================

Several ``cwms-cli`` commands use the same CDA connection arguments. This page
documents those shared options in one place.

Shared options
--------------

- ``--office`` or ``OFFICE``
- ``--api-root`` or ``CDA_API_ROOT``
- ``--api-key`` or ``CDA_API_KEY``

These are the standard API inputs used by commands such as ``csv2cwms``.

Environment setup
-----------------

.. raw:: html

   <details>
   <summary>Windows</summary>

.. code-block:: batch

   set CDA_API_KEY=your-api-key
   set CDA_API_ROOT=https://cwms-data.usace.army.mil/cwms-data
   set OFFICE=SWT

.. raw:: html

   </details>
   <details>
   <summary>Linux</summary>

.. code-block:: bash

   export CDA_API_KEY="your-api-key"
   export CDA_API_ROOT="https://cwms-data.usace.army.mil/cwms-data"
   export OFFICE="SWT"

.. raw:: html

   </details>

Notes
-----

- ``--office`` uses the ``OFFICE`` environment variable.
- ``--api-root`` uses the ``CDA_API_ROOT`` environment variable.
- ``--api-key`` uses the ``CDA_API_KEY`` environment variable.
- Commands may still expose additional non-API options such as config files,
  timezone selection, or dry-run behavior.

See also
--------

- :doc:`CLI reference <../cli>`
- :doc:`csv2cwms <csv2cwms>`
