Installation and Setup
======================

This page covers installing ``cwms-cli``, adding optional dependencies required
by certain subcommands, and getting to a first working ``csv2cwms`` run.

Install cwms-cli
----------------

Install the base CLI package:

.. code-block:: bash

   pip install cwms-cli

Some commands require additional libraries that are not installed with the base
package. You will be alerted to missing dependencies if you try to run a command that requires an optional library that is not installed. See the next section for more on this.

Install cwms-python for CWMS-backed commands
--------------------------------------------

Commands that talk to CWMS, including ``csv2cwms``, require
``cwms-python``:

.. code-block:: bash

   pip install cwms-python

If you plan to use USGS-related commands, additional packages may also be
required depending on the subcommand.

How missing dependencies are reported
-------------------------------------

``cwms-cli`` subcommands use dependency checks to detect whether optional
libraries are installed. If a required library is missing, the command will
stop and print a message naming the missing module and an install command.

For example, a command may tell you to run something like:

.. code-block:: bash

   pip install cwms-python

This means you do not have to guess which extra library is needed for a given
subcommand. The command will tell you.

Shared API inputs
-----------------

Most CWMS-backed commands use the same CDA connection inputs:

   - ``--office`` or ``OFFICE``
   - ``--api-root`` or ``CDA_API_ROOT``
   - ``--api-key`` or ``CDA_API_KEY``

See :doc:`Common API Arguments <api_arguments>` for environment setup examples.

csv2cwms config references
--------------------------

For ``csv2cwms``, start from one of these:

   - :doc:`Complete config example <csv2cwms_complete_config>`
   - :doc:`csv2cwms <csv2cwms>`

The complete config page documents the JSON structure, global defaults, and
supported per-file and per-timeseries keys.

If your source CSV contains commented lines, ``csv2cwms`` skips rows whose
first non-whitespace character is ``#`` automatically.

Real working example
--------------------

The repository includes sample ``csv2cwms`` test data that can be used as a
working example.

Sample CSV input
~~~~~~~~~~~~~~~~

.. literalinclude:: ../../cwmscli/commands/csv2cwms/tests/data/sample_brok.csv
   :language: text
   :lines: 1-6

Sample config
~~~~~~~~~~~~~

*Notice not ever column is used in this example!*

.. literalinclude:: ../../cwmscli/commands/csv2cwms/tests/data/sample_config.json
   :language: json

Example dry run
~~~~~~~~~~~~~~~

After installing ``cwms-cli`` and ``cwms-python``, and after setting the shared
API inputs described in :doc:`Common API Arguments <api_arguments>`, you can run:

.. code-block:: bash

   cwms-cli csv2cwms \
     --office SWT \
     --api-root https://cwms-data.usace.army.mil/cwms-data \
     --config cwmscli/commands/csv2cwms/tests/data/sample_config.json \
     --timezone America/Chicago \
     --dry-run

That example uses the sample config and sample CSV shipped in this repository
and is a good starting point for verifying that parsing, mapping, and logging
look correct before you point the command at a production config.

See also
--------

   - :doc:`csv2cwms <csv2cwms>`
   - :doc:`Common API Arguments <api_arguments>`
   - :doc:`Complete config example <csv2cwms_complete_config>`
