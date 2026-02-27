Blob commands
=============

Use ``cwms-cli blob`` to upload, download, delete, update, and list CWMS blobs.

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
