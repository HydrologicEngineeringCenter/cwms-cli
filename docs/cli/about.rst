What is cwms-cli?
==================

``cwms-cli`` is a Python package and command-line tool maintained by the U.S.
Army Corps of Engineers Hydrologic Engineering Center. It provides commands
for viewing, transferring, and updating data through the CWMS Data API (CDA),
along with tools for sources such as USGS and HEC-DSS.

Who uses it?
------------

``cwms-cli`` is intended for people who work with CWMS data, including water
managers, forecasters, data administrators, and system administrators. You do
not need to be a Python expert to use the command examples, although scripting
experience is useful for repeatable workflows.

Where does it run?
-------------------

You can install and run ``cwms-cli`` on a Windows workstation or on a CWMS
server such as a T7 system. The commands run from a terminal, PowerShell, or
another supported shell. See :doc:`setup` for installation and platform notes.

What access do I need?
----------------------

To use a CDA-backed command, you need the CDA API root for your target and
credentials accepted by that CDA instance. Most commands use an API key. Some
commands can use a saved browser login session. Your CDA account must also
have permission for the office and operation you are requesting. Installing
the package does not grant database access.

Next steps
----------

Start with :doc:`setup` and then choose a workflow from the project
documentation home page.

What can I do after installation?
---------------------------------

Once the CLI is installed and configured, you can use it to:

- retrieve USGS observations, ratings, and measurements and prepare them for
  CWMS;
- preview a CSV time-series import with ``csv2cwms --dry-run`` before writing
  data;
- copy locations, time-series identifiers, and values between CDA instances;
- inspect or update CWMS locations, users, offices, blobs, and CLOBs when your
  account has the required permissions; and
- transfer data with HEC-DSS or import SHEF configuration.

Each workflow guide includes command examples and links to the relevant
options. Start from the workflow table on the documentation home page when
you are not sure which command to choose.
