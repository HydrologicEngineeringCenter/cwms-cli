cwms-cli Documentation
======================

``cwms-cli`` provides command-line workflows for common CWMS and CDA tasks,
including CSV time-series loading, blob management, installation/update
helpers, and shared API argument handling.

Start here if you want to:

- install the CLI and optional dependencies
- learn which commands are available
- jump directly to task-specific guides and references

Quick Start
-----------

- :doc:`Installation and Setup <cli/setup>` for install steps, optional
  dependencies, shared CDA inputs, and a working ``csv2cwms`` example
- :doc:`CLI reference <cli>` for the full generated command reference
- :doc:`Common API Arguments <cli/api_arguments>` for shared CDA connection
  flags and environment variables

Task Guides
-----------

- :doc:`csv2cwms <cli/csv2cwms>` to load CSV time series into CDA
- :doc:`Blob commands <cli/blob>` to upload, download, list, delete, and
  update blobs
- :doc:`Load Location ids-all <cli/load_location_ids_all>` to copy locations
  selected from a source CDA catalog into a target CDA
- :doc:`Update command <cli/update>` to update the installed package with pip
- :doc:`Version argument <cli/version>` to print the installed version and see
  upgrade guidance

Reference Pages
---------------

- :doc:`CDA Regex Guide <cli/cda_regex>` for CDA regex syntax and usage
- :doc:`csv2cwms Complete Config Example <cli/csv2cwms_complete_config>` for
  the full JSON config structure
- :doc:`csv2cwms Supported Interval Identifiers <cli/csv2cwms_intervals>` for
  interval names accepted by ``csv2cwms``

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   cli/setup
   cli/shell_completion
   cli
   cli/api_arguments

.. toctree::
   :maxdepth: 2
   :caption: Command Guides

   cli/csv2cwms
   cli/blob
   cli/login
   cli/clob
   cli/users
   cli/load_location_ids_all
   cli/update
   cli/version

.. toctree::
   :maxdepth: 2
   :caption: Reference

   cli/cda_regex
   cli/csv2cwms_complete_config
   cli/csv2cwms_intervals
