Environment Manager
===================

Manage named CDA environments with ``cwms-cli env``. Each environment stores
a CDA API root URL, office code, and optional API key in a JSON file under
``~/.config/cwms-cli/envs/`` (or ``$XDG_CONFIG_HOME/cwms-cli/envs/`` when that
variable is set), on all platforms. Files are created with mode ``0600``
(owner-only read/write) so only your user account can read them.

This keeps API keys out of project directories, shell history, and command
lines, and lets you reference environments by name instead of juggling
URLs and credentials.


Built-in Environments
---------------------

``cwbi-prod`` ships preconfigured with the production CDA URL. It is
available immediately — no ``env setup`` required — and appears in
``env show`` as ``(built-in)``.

Because the built-in has no office or API key, you still need to pass
``--source-office`` when using it as a source:

.. code-block:: bash

   cwms-cli load location ids-all \
     --source-env cwbi-prod --source-office SWT \
     --target-env localhost

To avoid repeating ``--source-office`` every time, run ``env setup`` once
to attach an office (and optionally an API key):

.. code-block:: bash

   cwms-cli env setup cwbi-prod --office SWT --api-key YOUR_KEY


Quick Start
-----------

**1. Create environments:**

.. code-block:: bash

   # Production — customize the built-in with your office and key
   cwms-cli env setup cwbi-prod --office SWT --api-key YOUR_KEY

   # Development (needs --api-root)
   cwms-cli env setup cwbi-dev \
     --api-root https://cwms-data-dev.example.mil/cwms-data \
     --office SWT --api-key YOUR_KEY

   # Test (needs --api-root)
   cwms-cli env setup cwbi-test \
     --api-root https://cwms-data-test.example.mil/cwms-data \
     --office SWT --api-key YOUR_KEY

   # Local development server
   cwms-cli env setup localhost \
     --api-root http://localhost:8082/cwms-data --office DEV

**2. Use environments with load commands:**

.. code-block:: bash

   cwms-cli load location ids-all \
     --source-env cwbi-prod --target-env localhost

   cwms-cli load timeseries data \
     --source-env cwbi-prod --target-env localhost \
     --ts-id "Black Butte.Flow.Inst.1Hour.0.raw-cda"

**3. View and manage environments:**

.. code-block:: bash

   cwms-cli env show
   cwms-cli env delete old-env --yes


Using Environments with ``load``
---------------------------------

The ``--source-env`` and ``--target-env`` options resolve a named
environment into the corresponding source/target options:

- ``--source-env`` sets ``--source-cda`` and ``--source-office``
- ``--target-env`` sets ``--target-cda`` and ``--target-api-key``

These two invocations are equivalent:

.. code-block:: bash

   # Explicit flags
   cwms-cli load location ids-all \
     --source-cda https://cwms-data.usace.army.mil/cwms-data/ \
     --source-office SWT \
     --target-cda http://localhost:8082/cwms-data/ \
     --target-api-key "apikey 0123456789abcdef"

   # Named environments
   cwms-cli load location ids-all \
     --source-env cwbi-prod --target-env localhost

**Rules:**

- ``--source-env`` and ``--source-cda`` are mutually exclusive.
- ``--target-env`` and ``--target-cda`` are mutually exclusive.
- Explicit ``--source-office`` or ``--target-api-key`` flags override the
  values from the environment file.


Commands
--------

cwms-cli env setup <name>
~~~~~~~~~~~~~~~~~~~~~~~~~

Create or update an environment configuration.

.. code-block:: bash

   # Setup with all options
   cwms-cli env setup myenv \
     --api-root https://cwms-data-dev.example.mil/cwms-data \
     --api-key YOUR_KEY --office SWT

   # Update just the API key (other fields preserved)
   cwms-cli env setup myenv --api-key NEW_KEY

   # Update just the office
   cwms-cli env setup myenv --office LRD

``cwbi-prod`` is built-in and already has the production URL. Running
``env setup cwbi-prod`` creates a user file that overrides the built-in,
letting you attach an office and API key. All other environment names
require ``--api-root``.


cwms-cli env show
~~~~~~~~~~~~~~~~~

List all configured environments with their API root, office, and key status.
The API key is always redacted — only ``has API key`` or ``no API key`` is shown.

.. code-block:: bash

   cwms-cli env show

**Example output:**

.. code-block:: text

   Current environment: cwbi-prod

   Available environments:
   * cwbi-prod
       API Root: https://cwms-data.usace.army.mil/cwms-data
       Office:   SWT
       Status:   has API key
     cwbi-dev
       API Root: https://cwms-data-dev.example.mil/cwms-data
       Office:   SWT
       Status:   no API key

On a fresh install (before any ``env setup``), ``cwbi-prod`` appears with
``(built-in)`` and shows ``Office: not set``.

The ``*`` marks the currently active environment (from the ``ENVIRONMENT``
variable).

**Options:**

- ``--check`` — test connectivity and API key validity for each environment
  (requires network access). Adds ``Connect`` and ``Auth`` lines to the output.

.. code-block:: bash

   cwms-cli env show --check

.. code-block:: text

   Available environments:
   * cwbi-prod
       API Root: https://cwms-data.usace.army.mil/cwms-data
       Office:   SWT
       Status:   has API key
       Connect:  reachable (284ms)
       Auth:     authenticated
     cwbi-dev
       API Root: https://cwms-data-dev.example.mil/cwms-data
       Office:   SWT
       Status:   no API key
       Connect:  unreachable — Connection refused


cwms-cli env export <name>
~~~~~~~~~~~~~~~~~~~~~~~~~~

Export an environment's variables to your current shell or a file.

.. code-block:: bash

   # Load into the current bash/zsh shell
   eval "$(cwms-cli env export cwbi-prod --format bash)"

   # Load into PowerShell
   cwms-cli env export cwbi-prod --format powershell | Out-String | Invoke-Expression

   # Write a .env file for an IDE or docker-compose
   cwms-cli env export cwbi-prod --output .env

**Formats:** ``dotenv`` (default), ``bash``, ``powershell``, ``cmd``, ``fish``.

**Safety:** The API key is never printed to a terminal by default. If stdout
is a TTY and the environment has an API key, ``export`` shows shell-specific
recipes instead. Use ``--show-key`` to override, or ``--output FILE`` to write
directly to disk (recommended — guarantees ``0600`` permissions and no
scrollback exposure).

**Options:**

- ``--output FILE`` — write to a file with ``0600`` permissions instead of stdout.
- ``--no-key`` — omit ``CDA_API_KEY`` (useful for templates or sharing).
- ``--show-key`` — allow the API key to be displayed in the terminal.


cwms-cli env activate <name>
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Activate an environment in a new shell session.

.. code-block:: bash

   cwms-cli env activate cwbi-prod

This spawns a child shell with the environment variables set. Type ``exit``
or press ``Ctrl+D`` to return to your original shell.

.. note::

   The parent shell and any already-open IDE will **not** see these variables.
   For IDE integration, use ``cwms-cli env export <name> --output .env``
   instead.


cwms-cli env delete <name>
~~~~~~~~~~~~~~~~~~~~~~~~~~

Delete an environment configuration.

.. code-block:: bash

   # Delete with confirmation prompt
   cwms-cli env delete myenv

   # Delete without confirmation
   cwms-cli env delete myenv --yes


Storage and Security
--------------------

**File locations:**

- All platforms: ``~/.config/cwms-cli/envs/<name>.json``
  (respects ``XDG_CONFIG_HOME`` when set)

**File permissions:** ``0600`` on POSIX (owner-only read/write). On Windows,
an ACL restricts access to the current user.

**Security model:** The user account is the security boundary, matching
``aws``, ``gcloud``, ``kubectl``, and ``gh``. This feature defends against:

- Accidental ``git add`` of a key — files live in ``~/.config/``, not the repo
- Key pasted into an LLM — users share ``env show`` output (always redacted)
- Key visible in ``ps`` or shell history — users reference the env name, not values
- Key in terminal scrollback — ``export`` refuses TTY output by default

This feature does **not** defend against root access or same-user process
reads. For encrypted-at-rest storage, use a vault (1Password CLI, HashiCorp
Vault, AWS Secrets Manager) and feed values in via environment variables.


Headless and CI Usage
---------------------

For headless or CI environments where ``cwms-cli env`` is not practical,
set environment variables directly:

.. code-block:: bash

   export CDA_API_ROOT="https://cwms-data.usace.army.mil/cwms-data"
   export CDA_API_KEY="your_key"
   export OFFICE="SWT"

   cwms-cli blob list


.. click:: cwmscli.commands.env:env_group
   :prog: cwms-cli env
   :nested: full
