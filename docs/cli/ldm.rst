LDM commands
============

.. include:: ../_generated/maintainers/ldm.inc

``cwms-cli ldm`` manages products and product files in the CWBI Local Data
Manager (LDM) API. LDM is the cloud implementation of Unidata's Local Data
Manager used for CWMS data acquisition and dissemination.

Set the API root and application key in the environment before using the
commands:

.. code-block:: console

   set LDM_API_ROOT=https://ldm.example/api
   set LDM_API_KEY=your-application-key

The API key is sent in the ``key`` header. Do not put it in a script committed
to source control.

Products
--------

Product create and update payloads are JSON objects accepted by the LDM API.
The API documentation uses fields including ``name``, ``filename``,
``description``, ``enabled``, ``is_forecast``, ``pattern``, and nested
``feedtype.id`` and ``source.id`` values.

.. code-block:: console

   cwms-cli ldm product list
   cwms-cli ldm product get --product-slug coerr1lrn
   cwms-cli ldm product create --input-json product.json
   cwms-cli ldm product update --product-slug coerr1lrn --input-json product.json

Product files
-------------

Upload a file with the same multipart contract used by CWBI batch images:

.. code-block:: console

   cwms-cli ldm file upload \
     --product-slug coerr1lrn \
     --input-file report.shef

List files for a product, or query all files in a time window:

.. code-block:: console

   cwms-cli ldm file list --product-slug coerr1lrn
   cwms-cli ldm file list --start 2026-09-27T00:00:00Z --end 2026-09-27T12:00:00Z

The file list returns a ``file`` value such as
``products/coerr1lrn/report_123.shef``. Pass that value to download:

.. code-block:: console

   cwms-cli ldm file download \
     --file products/coerr1lrn/report_123.shef \
     --dest report.shef

The current LDM API does not implement product or product-file deletion. The
registered product-file ``DELETE`` route returns ``501 Not Implemented``, so
cwms-cli does not expose a delete command for LDM.
