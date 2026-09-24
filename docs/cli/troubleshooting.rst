Troubleshooting
===============

Command or dependency not found
----------------------------------------

Run ``python -m pip show cwms-cli`` in the environment where you installed the
CLI. Activate that environment before running ``cwms-cli --help``. Install
optional packages into the same environment using ``python -m pip``; see
:doc:`setup` for command-specific dependencies.

Use ``cwms-cli COMMAND --help`` to check option placement. Global flags precede
the command, for example ``cwms-cli --log-level DEBUG usgs timeseries --help``.

Connection failures
-------------------

Check that ``--api-root`` points to the CDA API root (usually ending in
``/cwms-data``), rather than a GUI or a resource such as ``/timeseries``.
For ``load`` commands, check ``--source-cda`` and ``--target-cda`` separately.
Verify required network/VPN access and service availability before retrying.

For certificate verification failures, configure Python's trusted CA bundle
for your organization. Requests-based calls accept ``REQUESTS_CA_BUNDLE``;
``login`` also provides ``--ca-bundle``. Follow the platform-specific guidance
printed by the CLI.

Authentication and permissions
------------------------------

- For HTTP 401, check credentials and the CDA target. If using saved login,
  run ``cwms-cli login --refresh`` or authenticate again with :doc:`login`.
- For HTTP 403, verify that the account has the required role for the office
  and operation. A successful login alone does not grant write access.
- Commands using the shared session helper prefer a saved login token over
  an API key. See :doc:`api_arguments` when diagnosing which credentials are used.

Unattended jobs and diagnostics
----------------------------------------

Use ``cwms-cli --non-interactive ...`` for scheduled jobs. Commands requiring
confirmation need their explicit arguments, such as ``update --yes`` or
``env delete NAME --yes``. See :doc:`api_arguments` for non-interactive behavior.

Capture logs by putting global options before the subcommand:

.. code-block:: bash

   cwms-cli --log-level DEBUG --log-file cwms-cli.log load timeseries data --help

Replace the command after the logging options with the failing invocation.
When reporting a problem, include the CLI version, command with credentials
removed, error text, and relevant log excerpts. Review logs for credentials
and private data before sharing them.
