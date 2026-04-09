Clob commands
=============

Use ``cwms-cli clob`` to upload, download, delete, update, and list CWMS clobs.

See also
--------

- :doc:`Blob commands <blob>`

Choose ``clob`` when you are working with text content such as configuration,
JSON, XML, notes, templates, or other character-based files that you want the
CLI to handle as text.

Choose :doc:`blob <blob>` when you are working with binary or media-oriented
files such as PDFs, images, spreadsheets, or other content where media type and
binary download behavior matter.

JSON deserves a specific note:

- Use :doc:`blob <blob>` for JSON when you want the payload treated as a typed
  artifact with media type such as ``application/json`` so downstream clients
  can recognize and handle it as JSON.
- Use ``clob`` for JSON when you mainly want to manage it as editable text
  through the CLI.

Quick reference
---------------

- ``clob upload`` stores text content from a local file.
- ``clob download`` writes the returned clob text to disk.
- ``clob list`` and ``clob download`` send an API key if one is configured,
  unless ``--anonymous`` is used.
- ``clob list --limit`` caps displayed rows, and sets the clob endpoint
  request page size unless ``--page-size`` is provided to override the fetch size.
- ``clob upload --overwrite`` replaces an existing clob.
- ``clob update`` supports partial updates and ``--ignore-nulls`` behavior.

Compared with :doc:`blob <blob>`, the ``clob`` command group is intentionally
smaller:

- no ``--media-type`` option
- no directory upload mode
- no generated IDs from file paths
- ``update`` supports ``--ignore-nulls`` instead of blob-style media updates

.. _clob-text-behavior:

Text behavior
-------------

``cwms-cli clob`` is the text-oriented companion to :doc:`blob <blob>`.

- Clob commands treat file content as text.
- ``clob download`` writes UTF-8 text output to the target file.
- Unlike :doc:`blob <blob>`, clob commands do not infer file extensions from a
  media type and do not perform binary decoding logic.

Example:

.. code-block:: bash

   cwms-cli clob download \
     --clob-id FEBRUARY_SUMMARY_JSON \
     --dest ./downloads/february-summary.json \
     --office SWT

.. _clob-auth-scope:

Auth and scope
--------------

Clob reads follow the same access pattern as :doc:`blob <blob>` reads.

- If ``--api-key`` is provided, or ``CDA_API_KEY`` is set, cwms-cli sends that key.
- If no key is provided, clob read commands default to anonymous access.
- Use ``--anonymous`` on ``clob download`` or ``clob list`` to force an anonymous read even when a key is configured.
- If a keyed read fails because the key scope is narrower than the content you are trying to view, the CLI logs a scope hint telling you to retry with ``--anonymous`` or remove the configured key.

Examples:

.. code-block:: bash

   # Use configured key, if present
   cwms-cli clob download --clob-id A.JSON --office SWT --api-root http://localhost:8082/cwms-data

   # Force anonymous read even if CDA_API_KEY is set
   cwms-cli clob download --clob-id A.JSON --office SWT --api-root http://localhost:8082/cwms-data --anonymous

   # Anonymous list
   cwms-cli clob list --office SWT --api-root http://localhost:8082/cwms-data --anonymous

List pagination
---------------

``cwms-cli clob list`` can cap the local output and also control how many rows
the CDA clob endpoint returns for the request.

- ``--limit`` caps how many rows cwms-cli prints or writes.
- When ``--limit`` is set, cwms-cli also uses that value as the clob endpoint
  request ``page_size``.
- Use ``--page-size`` to override the request size explicitly, especially if
  you want to fetch more rows than you plan to display.

Examples:

.. code-block:: bash

   # Fetch and show up to 250 rows
   cwms-cli clob list --office SWT --limit 250

   # Fetch 500 rows from CDA but only show the first 50 locally
   cwms-cli clob list --office SWT --limit 50 --page-size 500

.. _clob-overwrite-flag:

Overwrite behavior
------------------

``clob upload`` uses a normal Click flag pair:

- ``--overwrite`` replaces an existing clob
- ``--no-overwrite`` keeps the default behavior and fails if the clob already exists

Example:

.. code-block:: bash

   cwms-cli clob upload \
     --input-file ./config/ops-template.json \
     --clob-id OPS_TEMPLATE_JSON \
     --overwrite \
     --office SWT

.. _clob-update-behavior:

Update behavior
---------------

``clob update`` is intended for text metadata and text file changes.

- Use ``--description`` to replace the description field.
- Use ``--input-file`` to replace the stored clob text.
- Use ``--ignore-nulls`` to leave existing fields in place when the updated payload omits them.

Example:

.. code-block:: bash

   cwms-cli clob update \
     --clob-id OPS_TEMPLATE_JSON \
     --input-file ./config/ops-template.json \
     --description "Updated operational template" \
     --ignore-nulls \
     --office SWT

Special-character IDs
---------------------

Clob IDs that contain ``/`` or other characters that are not supported
in the URL path:

- cwms-cli detects those IDs automatically.
- For path-sensitive operations such as download, update, and delete, the CLI
  uses the CDA fallback pattern with an ``ignored`` path segment and the clob ID
  in the query string.
- You can still use the normal ``--clob-id`` argument from the CLI.

Example:

.. code-block:: bash

   cwms-cli clob download \
     --clob-id "OPS/TEMPLATES/CONFIG.JSON" \
     --dest ./downloads/config.json \
     --office SWT

Blob vs clob
------------

Use :doc:`blob <blob>` when you need:

- binary-safe upload and download
- media type tracking
- explicit JSON-friendly media type handling such as ``application/json``
- extension inference on download
- directory upload with regex matching and generated IDs

Use ``clob`` when you need:

- plain text upload and download
- human-readable file content handled as text
- simple text updates without blob media handling


.. click:: cwmscli.commands.commands_cwms:clob_group
   :prog: cwms-cli clob
   :nested: full
