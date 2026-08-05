Update command
==============

.. include:: ../_generated/maintainers/update.inc

Use ``cwms-cli update`` to update the installed ``cwms-cli`` package with pip.
By default it installs the latest available release, and you can optionally
target a specific version with ``--target-version``. After updating, use
:doc:`Version argument <version>` to confirm the installed version.

Before asking for confirmation, the command displays the Python executable,
environment prefix and type, and package location that will be updated. The
update runs pip through that displayed executable (``python -m pip``), so it
targets the same Python environment that is running ``cwms-cli``. This is
especially useful when multiple Python installations or virtual environments
are present.

On Windows, the command launches the pip install in a separate command window so
the running ``cwms-cli.exe`` does not block its own replacement.

.. note::

   A standalone ``pip install --upgrade cwms-cli`` command uses whichever
   ``pip`` executable appears first on the shell's path, which may belong to a
   different Python environment. Prefer ``cwms-cli update``. When updating
   manually, use the full Python executable displayed by ``cwms-cli update``
   with ``-m pip install --upgrade cwms-cli``.

Examples
--------

- Prompt before updating:

  ``cwms-cli update``

- Skip confirmation prompt:

  ``cwms-cli update --yes``

- Install a specific version:

  ``cwms-cli update --target-version 0.3.7 --yes``

- Include pre-release versions:

  ``cwms-cli update --pre --yes``

See also
--------

- :doc:`Version argument <version>`

.. click:: cwmscli.commands.commands_cwms:update_cli_cmd
   :prog: cwms-cli update
   :nested: full
