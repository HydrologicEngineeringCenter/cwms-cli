Users commands
==============

The ``cwms-cli users`` command group is the entry point for CWMS user-management
operations in the CLI.

Landing page
------------

## ``cwms-cli users roles``. 

This command lists the assignable roles returned by the CWMS Data API for the current credentials.

In practice, ``cwms-cli users roles`` and ``cwms.get_roles()`` typically return
the same role catalog regardless of office. Office context still matters for
actual user-role assignment work, but the role list itself is usually the same
for any given office.

If the command returns a permission error, use an API key for a user with
user-management admin access such as ``CWMS User Admins``. You can alter this in server admin or by reaching out to your region's CWMS administrator.

Examples
--------

- List the available user-management roles:

  ``cwms-cli users roles --office SPK --api-root http://localhost:8082/cwms-data/ --api-key <ADMIN_KEY>``

- Use API keys from the environment instead of a command-line arguments:

  ``cwms-cli users roles``

See also
--------

- :doc:`CLI reference <../cli>`

.. click:: cwmscli.commands.commands_cwms:users_group
   :prog: cwms-cli users
   :nested: full
