Login command
=============

Use ``cwms-cli login`` to start the CWBI OIDC PKCE flow and save the resulting
session for reuse. The command already has working defaults for the provider,
client ID, scope, callback host, callback port, timeout, and the
provider-specific token file path under ``~/.config/cwms-cli/auth/``.

By default, cwms-cli discovers the OIDC realm from the target CDA API's OpenAPI
spec at ``<api-root>/swagger-docs`` and caches the discovered value locally.

By default, the callback listener starts at port ``5555`` and automatically
tries up to three subsequent ports if earlier ones are already in use.

If a browser cannot be opened automatically, the command prints the
authorization URL so the user can continue manually.

Examples
--------

- Use the default login settings:

  ``cwms-cli login``

- Print the authorization URL instead of opening a browser:

  ``cwms-cli login --no-browser``

- Use the ``login.gov`` identity provider hint:

  ``cwms-cli login --provider login.gov``

- Save the session to a custom file:

  ``cwms-cli login --token-file ~/.config/cwms-cli/auth/custom-login.json``

- Change the local callback listener host and port:

  ``cwms-cli login --redirect-host 127.0.0.1 --redirect-port 6000``

- Override the client ID and scopes:

  ``cwms-cli login --client-id cwms --scope "openid profile"``

- Discover OIDC configuration from a different CDA target:

  ``cwms-cli login --api-root https://cwms-data.usace.army.mil/cwms-data``

- Wait longer for the callback during manual authentication:

  ``cwms-cli login --timeout 300 --no-browser``

- Use a custom CA bundle for TLS verification:

  ``cwms-cli login --ca-bundle /path/to/ca-bundle.pem``

- Refresh an existing saved session without opening a browser:

  ``cwms-cli login --refresh``

.. click:: cwmscli.commands.commands_cwms:login_cmd
   :prog: cwms-cli login
   :nested: full
