Update command
==============

.. include:: ../_generated/maintainers/update.inc

Use ``cwms-cli update`` to update the installed ``cwms-cli`` package with pip.
By default it installs the latest available release, and you can optionally
target a specific version with ``--target-version``. After updating, use
:doc:`Version argument <version>` to confirm the installed version.

On Windows, the command launches the pip install in a separate command window so
the running ``cwms-cli.exe`` does not block its own replacement.

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
