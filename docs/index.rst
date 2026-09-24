cwms-cli Documentation
======================

``cwms-cli`` loads and manages CWMS data through the CWMS Data API (CDA).
Start with :doc:`cli/setup`, then choose a workflow below. For every command's
options and defaults, use the generated :doc:`cli` or ``cwms-cli --help``.

Choose a workflow
-----------------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Task
     - Guide
   * - Connect to CDA and authenticate
     - :doc:`cli/api_arguments`, :doc:`cli/login`, :doc:`cli/env`
   * - Load CSV observations
     - :doc:`cli/csv2cwms`
   * - Copy locations or time series between CDA instances
     - :doc:`cli/load_location_ids_all`, :doc:`cli/load_timeseries`
   * - Transfer data to or from HEC-DSS
     - :doc:`cli/dss`
   * - Retrieve USGS observations, ratings, or measurements
     - :doc:`cli/usgs`
   * - Import SHEF acquisition or export configuration
     - :doc:`cli/shef`
   * - Manage binary files or text stored in CWMS
     - :doc:`cli/blob`, :doc:`cli/clob`
   * - Manage users and office roles
     - :doc:`cli/users`
   * - Check or update the installed version
     - :doc:`cli/version`, :doc:`cli/update`

.. toctree::
   :maxdepth: 1
   :caption: Getting Started

   cli/setup
   cli/api_arguments
   cli/login
   cli/env
   cli/shell_completion
   cli/troubleshooting

.. toctree::
   :maxdepth: 1
   :caption: Data Loading and Transfers

   cli/csv2cwms
   cli/load_location_ids_all
   cli/load_timeseries
   cli/dss
   cli/usgs
   cli/shef

.. toctree::
   :maxdepth: 1
   :caption: Data and User Management

   cli/blob
   cli/clob
   cli/users

.. toctree::
   :maxdepth: 1
   :caption: Reference

   cli
   cli/cda_regex
   cli/csv2cwms_complete_config
   cli/csv2cwms_intervals
   cli/version
   cli/update

.. toctree::
   :maxdepth: 1
   :caption: Development

   cli/version_guard
