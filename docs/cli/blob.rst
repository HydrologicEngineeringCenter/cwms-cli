Blob commands
=============

.. include:: ../_generated/maintainers/blob.inc

Use ``cwms-cli blob`` to upload, download, delete, update, and list CWMS blobs.

Quick reference
---------------

- ``blob upload`` supports single-file upload and directory upload.
- ``blob download`` writes the returned blob content to disk using the server media type when possible.
- ``blob list`` and ``blob download`` send an API key if one is configured, unless ``--anonymous`` is used.
- Directory upload stops before sending anything if generated blob IDs would collide.
- ``blob upload --overwrite``: To replace existing blobs.

.. _blob-download-behavior:

Download behavior
-----------------

``cwms-cli blob download`` stores the content returned by the CDA blob endpoint.

- Text responses are written as text.
- Binary responses are written as bytes.
- If the destination path has no extension, cwms-cli will try to infer one from the blob media type.

Example:

.. code-block:: bash

   cwms-cli blob download \
     --blob-id FEBRUARY_SUMMARY \
     --dest ./downloads/february-summary \
     --office SWT

.. _blob-auth-scope:

Auth and scope
--------------

Blob reads can behave differently depending on whether an API key is sent.

- If ``--api-key`` is provided, or ``CDA_API_KEY`` is set, cwms-cli sends that key.
- If no key is provided, blob read commands default to anonymous access.
- Use ``--anonymous`` on ``blob download`` or ``blob list`` to force an anonymous read even when a key is configured.
- If a keyed read fails because the key scope is narrower than the content you are trying to view, the CLI logs a scope hint telling you to retry with ``--anonymous`` or remove the configured key.

Examples:

.. code-block:: bash

   # Use configured key, if present
   cwms-cli blob download --blob-id A.TXT --office SWT --api-root http://localhost:8082/cwms-data

   # Force anonymous read even if CDA_API_KEY is set
   cwms-cli blob download --blob-id A.TXT --office SWT --api-root http://localhost:8082/cwms-data --anonymous

   # Anonymous list
   cwms-cli blob list --office SWT --api-root http://localhost:8082/cwms-data --anonymous

.. _blob-upload-modes:

Upload modes
------------

The ``upload`` command supports two modes:

1. Single file upload with explicit blob ID (existing behavior)
2. Directory upload with regex matching (bulk behavior)

Single file upload
~~~~~~~~~~~~~~~~~~

Use ``--input-file`` and ``--blob-id``:

.. code-block:: bash

   cwms-cli blob upload \
     --input-file ./reports/february-summary.pdf \
     --blob-id FEBRUARY_SUMMARY \
     --office SWT

Directory upload with regex
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``--input-dir`` with ``--file-regex``:

.. code-block:: bash

   cwms-cli blob upload \
     --input-dir ./incoming \
     --file-regex '.*\.json$' \
     --office SWT
     
Important behavior for bulk uploads:

- Regex is matched against each file path relative to ``--input-dir``.
- By default only the top level of ``--input-dir`` is scanned.
- Add ``--recursive`` to include subdirectories.
- Blob IDs are auto-generated from relative paths:
  ``subdir/file.json`` -> ``SUBDIR_FILE``.
- Add ``--blob-id-prefix`` to prepend text to generated IDs.
- Uploads run one file at a time.
- If one file fails, upload continues for remaining files.
- Command exits non-zero if any file fails.

.. _blob-bulk-collisions:

Bulk upload collisions
----------------------

Directory upload generates blob IDs from the matched relative file paths.

- ``subdir/file.json`` becomes ``SUBDIR_FILE``
- ``a.txt`` and ``a.json`` both become ``A``
- ``dir/a.txt`` and ``dir_a.txt`` both become ``DIR_A``

cwms-cli now checks for these collisions before uploading anything.

- If two or more matched files would produce the same blob ID, the command stops immediately.
- No files are uploaded when this happens.
- Use ``--blob-id-prefix`` only when it actually makes the generated IDs unique.

Example:

.. code-block:: bash

   cwms-cli blob upload \
     --input-dir ./incoming \
     --file-regex '.*' \
     --blob-id-prefix OPS_ \
     --office SWT

.. _blob-overwrite-flag:

Overwrite behavior
------------------

``blob upload`` uses a normal Click flag pair:

- ``--overwrite`` replaces an existing blob
- ``--no-overwrite`` keeps the default behavior and fails if the blob already exists

Example:

.. code-block:: bash

   cwms-cli blob upload \
     --input-file ./reports/february-summary.pdf \
     --blob-id FEBRUARY_SUMMARY \
     --overwrite \
     --office SWT

Regex vs shell wildcards
------------------------

``--file-regex`` expects a Python regular expression, not a shell wildcard.

- Shell wildcard example: ``*.json`` (not valid regex for this option)
- Regex equivalent: ``.*\.json$``

Quote regex patterns in your terminal so the shell does not expand characters
before ``cwms-cli`` receives them.

Examples:

.. code-block:: bash

   # Match only JSON files in top-level input dir
   --file-regex '.*\.json$'

   # Match PDF or PNG files recursively
   --recursive --file-regex '.*\.(pdf|png)$'

   # Match only files under a subfolder inside input dir
   --recursive --file-regex '^reports/.+\.csv$'

References:

- Python regex documentation: https://docs.python.org/3/library/re.html
- Bash pattern matching (globs): https://www.gnu.org/software/bash/manual/bash.html#Pattern-Matching
- Bash quoting rules: https://www.gnu.org/software/bash/manual/bash.html#Quoting


.. click:: cwmscli.commands.commands_cwms:blob_group
   :prog: cwms-cli blob
   :nested: full
