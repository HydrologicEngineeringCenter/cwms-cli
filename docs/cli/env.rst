Environment Manager
===================

Secure environment management for CDA environments using system keyring storage.

Overview
--------

The environment manager stores your CDA API credentials and configuration securely using your system's keyring:

- **Linux**: gnome-keyring, kwallet, or secretstorage
- **macOS**: Keychain (built-in)
- **Windows**: Credential Manager (built-in)
- **Solaris**: Keyring not available - use environment variables (see Headless/CI Usage below)

This keeps API keys out of plaintext files and provides a consistent, secure experience across platforms.

Suggested Environments
----------------------

**Pre-configured (have default URLs):**

- ``cwbi-prod`` - Production CWBI (https://cwms-data.usace.army.mil/cwms-data)

**Need --api-root:**

- ``cwbi-dev`` - Development CWBI
- ``cwbi-test`` - Test CWBI
- ``localhost`` - Local development server (port varies: 8081, 8082, etc.)
- ``onsite`` - Local non-cloud server
- Custom environment names

Quick Start
-----------

**1. Setup environments:**

.. code-block:: bash

   # Pre-configured environment (just add key/office)
   cwms-cli env setup cwbi-prod --office SWT --api-key YOUR_KEY

   # Custom environments (need --api-root)
   cwms-cli env setup cwbi-dev --api-root https://cwms-data-dev.example.mil/cwms-data --office SWT --api-key YOUR_KEY
   cwms-cli env setup localhost --api-root http://localhost:8082/cwms-data --office DEV

**2. Activate an environment:**

.. code-block:: bash

   cwms-cli env activate cwbi-dev

This spawns a new shell with the environment variables set. When you're done, type ``exit`` to return to your original shell.

**3. View environments:**

.. code-block:: bash

   # List all environments with their API roots
   cwms-cli env show

Commands
--------

cwms-cli env setup <name>
~~~~~~~~~~~~~~~~~~~~~~~~~~

Create or update an environment configuration.

.. code-block:: bash

   # Setup with all options
   cwms-cli env setup myenv --api-root https://cwms-data-dev.example.mil/cwms-data  --api-key YOUR_KEY --office SWT

   # Update just the API key
   cwms-cli env setup myenv --api-key NEW_KEY

   # Update just the office
   cwms-cli env setup myenv --office LRD

cwms-cli env show
~~~~~~~~~~~~~~~~~~

List all configured environments.

.. code-block:: bash

   # List all environments with API roots and key status
   cwms-cli env show

**Output:**

.. code-block:: text

   Current environment: cwbi-prod

   Available environments:
   * cwbi-prod
       API Root: https://cwms-data.usace.army.mil/cwms-data
       Office: SWT
       Status: has API key
     cwbi-dev
       API Root: https://cwms-data-dev.example.mil/cwms-data
       Office: SWT
       Status: no API key

The ``*`` marks the currently active environment.

cwms-cli env activate <name>
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Activate an environment in a new shell session.

.. code-block:: bash

   cwms-cli env activate cwbi-prod

The environment variables will be set in the new shell and persist until you exit:

.. code-block:: bash

   # Now in the activated environment
   echo $CDA_API_ROOT    # Shows the API root
   cwms-cli blob list     # Uses environment config

   # Exit to return to original shell
   exit

**Benefits:**

- Clean separation between environments
- Original shell remains unchanged
- Type ``exit`` to immediately return to original state

cwms-cli env delete <name>
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Delete an environment configuration from keyring.

.. code-block:: bash

   # Delete with confirmation prompt
   cwms-cli env delete myenv

   # Delete without confirmation
   cwms-cli env delete myenv --yes

How It Works
------------

**Secure storage:** Configuration is stored in your system's keyring:

- ``~/.local/share/keyrings/`` (Linux with GNOME Keyring)
- ``~/Library/Keychains/`` (macOS Keychain)
- Windows Credential Manager (Windows)

**Environment variables set when activated:**

- ``ENVIRONMENT`` - Environment name
- ``CDA_API_ROOT`` - API root URL
- ``CDA_API_KEY`` - API key (if provided)
- ``OFFICE`` - Default office (if provided)

**Usage with other commands:**

.. code-block:: bash

   # Activate environment (spawns new shell)
   cwms-cli env activate cwbi-prod

   # Now run commands (uses environment variables automatically)
   cwms-cli blob list
   cwms-cli users list

   # Command flags override environment variables
   cwms-cli blob list --api-root https://cwms-data.usace.army.mil/cwms-data

   # Exit the environment shell
   exit

**Variable persistence:**

- Variables persist until you ``exit`` the spawned shell
- Variables do NOT affect your original shell
- Variables do NOT persist across terminal restarts (activate again when needed)

Headless/CI Usage (and Solaris)
--------------------------------

For headless, CI, or Solaris environments where keyring is not available, set environment variables directly:

.. code-block:: bash

   export CDA_API_ROOT="https://cwms-data.usace.army.mil/cwms-data"
   export CDA_API_KEY="your_key"
   export OFFICE="SWT"

   # Commands will use these variables
   cwms-cli blob list

The CLI will automatically fall back to reading from ``os.environ`` when keyring is unavailable.

**Note for Solaris users:** Since system keyring backends are not available on Solaris, you must use this environment variable approach. The ``cwms-cli env setup`` and ``cwms-cli env activate`` commands will not work without a keyring backend. Instead, set the variables directly in your shell profile (e.g., ``~/.bashrc`` or ``~/.profile``).

.. click:: cwmscli.commands.env:env_group
   :prog: cwms-cli env
   :nested: full
