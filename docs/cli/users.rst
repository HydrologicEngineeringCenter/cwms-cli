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

Add a role to a user
--------------------

Use ``cwms-cli users roles add`` to add one or more roles to an existing user
for an office. This command maps to the CWMS user-management POST operation on
``/user/{user-name}/roles/{office-id}``.

Before sending the request, the CLI validates that:

- the target user exists in the CDA ``/users`` catalog
- each requested role exists in the CDA ``/roles`` catalog

Interactive mode
~~~~~~~~~~~~~~~~

Run the add command without add-specific arguments to use the interactive flow:

``cwms-cli users roles add``

The interactive flow will:

- Ask if the office you have set is the one you want to use
- let you override that office before the request is sent
- prompt for the user name
- show the available roles
- let you enter one or more roles to add

Argument mode
~~~~~~~~~~~~~

If you already know the values you want, you can pass them directly:

``cwms-cli users roles add --office SPK --api-root http://localhost:8082/cwms-data/ --api-key <ADMIN_KEY> --user-name q0hectest --roles "CWMS User Admins" --roles "Viewer Users"``

You can also pass roles as a comma-separated list:

``cwms-cli users roles add --office SPK --api-root http://localhost:8082/cwms-data/ --api-key <ADMIN_KEY> --user-name q0hectest --roles "CWMS User Admins,Viewer Users"``

All-or-none add arguments
~~~~~~~~~~~~~~~~~~~~~~~~~

For add-specific options, provide all required values or none of them.

Delete roles from a user
------------------------

Use ``cwms-cli users roles delete`` to delete one or more roles from an existing
user for an office. This command maps to the CWMS user-management DELETE
operation on ``/user/{user-name}/roles/{office-id}``.

Before sending the request, the CLI validates that:

- the target user exists in the CDA ``/users`` catalog
- each requested role exists in the CDA ``/roles`` catalog

Interactive mode
~~~~~~~~~~~~~~~~

Run the delete command without delete-specific arguments to use the interactive
flow:

``cwms-cli users roles delete``

The interactive flow will:

- ask if the office you have set is the one you want to use
- let you override that office before the request is sent
- prompt for the user name
- show the available roles
- let you enter one or more roles to delete

Argument mode
~~~~~~~~~~~~~

If you already know the values you want, you can pass them directly:

``cwms-cli users roles delete --office SPK --api-root http://localhost:8082/cwms-data/ --api-key <ADMIN_KEY> --user-name q0hectest --roles "CWMS User Admins" --roles "Viewer Users"`` 

You can also pass roles as a comma-separated list:

``cwms-cli users roles delete --user-name q0hectest --roles "CWMS User Admins,Viewer Users"`` 

All-or-none delete arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For delete-specific options, provide all required values or none of them.


See also
--------

- :doc:`CLI reference <../cli>`

.. click:: cwmscli.commands.commands_cwms:users_group
   :prog: cwms-cli users
   :nested: full
