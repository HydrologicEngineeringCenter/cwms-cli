Common API Arguments
====================

Several ``cwms-cli`` commands use the same CDA connection arguments. This page
documents those shared options in one place.

Shared options
--------------

- ``--office`` or ``OFFICE``
- ``--api-root`` or ``CDA_API_ROOT``
- ``--api-key`` or ``CDA_API_KEY``

Some commands also expose ``--api-key-loc`` / ``-kl`` to read the API key from
the first line of a file instead of passing the key inline. This is currently
available on USGS, SHEF, and user-management subcommands.

These are the standard API inputs used by commands such as ``csv2cwms``.
Commands using the shared session helper prefer the saved
access token from ``~/.config/cwms-cli/auth/federation-eams.json`` over an API
key. If no saved token is available, it falls back to the configured API key.

``load`` uses separate ``--source-cda`` / ``CDA_SOURCE_URL`` and
``--target-cda`` / ``CDA_TARGET_URL`` inputs, plus ``--source-office`` /
``CDA_SOURCE_OFFICE`` and ``--target-api-key`` / ``CDA_API_KEY``. See
:doc:`load_location_ids_all`, :doc:`load_timeseries`, and :doc:`env`.

Environment setup
-----------------

.. raw:: html

   <details>
   <summary>Windows Command Prompt</summary>

.. code-block:: batch

   set CDA_API_KEY=your-api-key
   set CDA_API_ROOT=https://cwms-data.usace.army.mil/cwms-data
   set OFFICE=SWT

.. raw:: html

   </details>
   <details>
   <summary>PowerShell</summary>

.. code-block:: powershell

   $env:CDA_API_KEY = "your-api-key"
   $env:CDA_API_ROOT = "https://cwms-data.usace.army.mil/cwms-data"
   $env:OFFICE = "SWT"

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

Windows notes
-------------

The ``set`` and ``$env:`` examples above set variables only in the current
Command Prompt or PowerShell session. Open a new terminal, restart the
computer, or start a script from another application and those variables will
not be present unless you configure them again.

For repeatable use, store the connection with ``cwms-cli env setup`` and start
a child shell with ``cwms-cli env activate NAME``. Run the CLI commands from
that child shell. Closing it ends that activation, while the saved environment
remains available for the next activation. You can also export a named
environment for a specific PowerShell session:

.. code-block:: powershell

   cwms-cli env export prod --format powershell | Out-String | Invoke-Expression

Installing ``cwms-cli`` does not create an API key or grant CDA access. Ask
your office or CDA administrator for the correct API root, office, and key.

Notes
-----

- ``--office`` uses the ``OFFICE`` environment variable.
- ``--api-root`` uses the ``CDA_API_ROOT`` environment variable.
- ``--api-key`` uses the ``CDA_API_KEY`` environment variable.
- When ``--api-key-loc`` is provided for a command that supports it, the key
  read from that file takes precedence over ``--api-key`` and over a
  ``CDA_API_KEY`` value coming from the environment.
- When using the shared session helper, a saved login token takes precedence over
  ``--api-key``, ``--api-key-loc``, or ``CDA_API_KEY``.
- For CDA-backed regex filters such as ``--like``, ``--location-kind-like``, and ``--timeseries-id-regex``, see the :doc:`CWMS Data API regular expression guide <cda_regex>`.
- Commands may still expose additional non-API options such as config files,
  timezone selection, or dry-run behavior.

Global logging and debug options
--------------------------------

Use the top-level ``cwms-cli --log-level`` option to control CLI log verbosity.

Valid values are:

- ``DEBUG``
- ``INFO``
- ``WARNING``
- ``ERROR``
- ``CRITICAL``

Example:

.. code-block:: bash

   cwms-cli --log-level DEBUG csv2cwms \
     --office SWT \
     --api-root https://cwms-data.usace.army.mil/cwms-data \
     --config cwmscli/commands/csv2cwms/tests/data/sample_config.json \
     --dry-run

If you were looking for a ``--debug-level`` flag, use ``--log-level DEBUG``
instead.

If you are authenticated with CDA and have the ``SHOW STACK TRACE`` role you
will be able to see stack traces if your CDA version supports it. A given instance
of CDA must also have this feature enabled. You only see traces in DEBUG log level.

For certain exception paths, ``cwms-cli`` also checks ``CWMS_CLI_DEBUG``. When
that environment variable is set to ``1``, ``true``, ``yes``, or ``on``, the
CLI enables the same debug exception behavior. If CDA does not provide a server
stack trace, cwms-cli keeps the raw local exception behavior for diagnosis.

Headless and non-interactive use
--------------------------------

``cwms-cli`` automatically disables input prompts when standard input is not a
terminal or when it detects a common CI environment. You can also enable this
behavior explicitly with the top-level ``--non-interactive`` option or the
``CWMS_CLI_NON_INTERACTIVE=1`` environment variable. Use ``--interactive`` to
override automatic detection when you intentionally want to answer prompts.

Commands that would normally request confirmation fail immediately in
non-interactive mode and explain which arguments are required. For example,
``cwms-cli update`` and ``cwms-cli env delete`` require ``--yes`` before they
make changes. User-role changes must provide both ``--user-name`` and
``--roles``.

Color is disabled automatically when output is not a terminal. It can also be
disabled with the top-level ``--no-color`` option, a ``NO_COLOR`` environment
variable, or ``--log-file``.

``cwms-cli login --no-browser`` prints the authorization URL instead of opening
a browser. Login waits only for the configured ``--timeout`` while receiving
the local callback. For unattended jobs, prefer a saved refresh session or an
API key instead of starting a new browser login.

See also
--------

- :doc:`CLI reference <../cli>`
- :doc:`csv2cwms <csv2cwms>`
- :doc:`troubleshooting`
