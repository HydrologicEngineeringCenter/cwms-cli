Update command
==============

Use ``cwms-cli update`` to update the installed ``cwms-cli`` package with pip.
After updating, use :doc:`Version argument <version>` to confirm the installed
version.

Examples
--------

- Prompt before updating:

  ``cwms-cli update``

- Skip confirmation prompt:

  ``cwms-cli update --yes``

- Include pre-release versions:

  ``cwms-cli update --pre --yes``

See also
--------

- :doc:`Version argument <version>`

.. click:: cwmscli.commands.commands_cwms:update_cli_cmd
   :prog: cwms-cli update
   :nested: full
