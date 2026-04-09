Installation and Setup
======================

This page covers installing ``cwms-cli``, adding optional dependencies required
by certain subcommands, and configuring the shared CDA connection inputs used
across CWMS-backed commands.

Install cwms-cli
----------------

Install the base CLI package:

.. code-block:: bash

   pip install cwms-cli

After installation, see :doc:`Shell Completion <shell_completion>` if you want
tab completion for supported shells.

Some commands require additional libraries that are not installed with the base
package. You will be alerted to missing dependencies if you try to run a
command that requires an optional library that is not installed. See the next
section for more on this.

Install cwms-python for CWMS-Backed Commands
--------------------------------------------

Commands that talk to CWMS, including ``csv2cwms``, require
``cwms-python``:

.. code-block:: bash

   pip install cwms-python

If you plan to use USGS-related commands, additional packages may also be
required depending on the subcommand.

How Missing Dependencies Are Reported
-------------------------------------

``cwms-cli`` subcommands use dependency checks to detect whether optional
libraries are installed. If a required library is missing, the command will
stop and print a message naming the missing module and an install command.

For example, a command may tell you to run something like:

.. code-block:: bash

   pip install cwms-python

This means you do not have to guess which extra library is needed for a given
subcommand. The command will tell you.

Shared API Inputs
-----------------

Most CWMS-backed commands use the same CDA connection inputs:

- ``--office`` or ``OFFICE``
- ``--api-root`` or ``CDA_API_ROOT``
- ``--api-key`` or ``CDA_API_KEY``

See :doc:`Common API Arguments <api_arguments>` for environment setup examples.

See also
--------

- :doc:`Shell Completion <shell_completion>`
- :doc:`csv2cwms <csv2cwms>`
- :doc:`Common API Arguments <api_arguments>`
