Login command
=============

Use ``cwms-cli login`` to start the CWBI OIDC PKCE flow and save the resulting
session for reuse. The command already has working defaults for the provider,
client ID, scope, callback host, callback port, timeout, and token storage.

Login uses ``CDA_API_ROOT`` from the active environment unless ``--api-root``
is supplied. When ``ENVIRONMENT`` is set, access and refresh tokens are stored
inside ``~/.config/cwms-cli/envs/<ENVIRONMENT>.json`` alongside the environment's
configuration. Each named environment keeps its own login, even when two names
use the same API root. Without ``ENVIRONMENT``, sessions are stored in
``~/.config/cwms-cli/login.json``, one directory above ``envs/``.

Both kinds of file keep sessions indexed by API root, so an explicit API-root
override cannot overwrite or reuse another root's tokens. Trailing slashes are
ignored. Named environments do not fall back to the default login file. Both
identity providers use the same session slot for a given environment and root.
``XDG_CONFIG_HOME`` overrides the config directory on all platforms.

Switch with ``env activate`` or ``env export``. Returning to an environment
reuses its saved token, refreshing it when expired. ``env show`` reports local
login/token state, remaining access and refresh lifetimes, refresh expiry, and
token-file locations without network calls. It also lists default logins.
``env check`` (also ``env show --check``)
checks connectivity and calls the protected ``/roles`` endpoint using the saved
token, or the environment's API key when no usable token is available.
Token values are never included in these status displays or environment exports.
Updating an environment with ``env setup`` preserves its saved sessions;
deleting its environment file also deletes its sessions.

Older provider-only login files do not identify their CDA API root and are not
automatically reused. Run ``cwms-cli login`` once for each environment after
upgrading. Explicit ``--token-file`` paths remain supported for login and
refresh, but are not automatically selected by other commands or ``env check``.

By default, cwms-cli discovers the OIDC realm from the target CDA API's OpenAPI
spec at ``<api-root>/swagger-docs`` and caches the discovered value locally.

By default, the callback listener starts at port ``5555`` and automatically
tries up to three subsequent ports if earlier ones are already in use.

If a browser cannot be opened automatically, the command prints the
authorization URL so the user can continue manually.

Examples
--------

- Inspect the current environment's saved login without contacting the server:

  ``cwms-cli login --status``

  Shows local login state, access-token availability and remaining lifetime,
  refresh-session time remaining and expiration, and the absolute token-file
  location. Missing, expired, and unknown lifetimes are labeled explicitly.
  This does not verify server acceptance or refresh the session.

- Print just the current token-file location (even before logging in):

  ``cwms-cli login --token-location``

  Both inspection options honor ``CDA_API_ROOT``, ``--api-root``, and
  ``--token-file``. They never print token values and cannot be combined with
  ``--refresh`` or with each other.

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
