Installation
============

ML Research Tools can be installed from PyPI or directly from source using Poetry.

From PyPI (Recommended)
----------------------

The recommended way to install ML Research Tools is through PyPI:

.. code-block:: bash

   pip install ml_research_tools

From Source
----------

To install from source:

.. code-block:: bash

   git clone https://github.com/alexdremov/ml_research_tools.git
   cd ml_research_tools
   poetry install

Development Installation
----------------------

For development purposes, install with additional development dependencies:

.. code-block:: bash

   poetry install --with dev

This will install additional packages needed for development, such as testing and code quality tools.

Optional Dependencies
-------------------

The package has optional dependencies for different functionalities:

Documentation Tools
~~~~~~~~~~~~~~~~~~

For building documentation:

.. code-block:: bash

   poetry install --with docs

All Optional Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~

To install all optional dependencies:

.. code-block:: bash

   poetry install --all-extras

Verifying Installation
--------------------

After installation, verify by running:

.. code-block:: bash

   poetry run ml_research_tools --help

This should display the help message with all available tools and options.

Requirements
-----------

ML Research Tools requires:

* Python 3.10 or later
* Poetry for dependency management

Optional Dependencies
-------------------

Depending on which tools you use, you may need:

* Redis (for caching functionality)
* LaTeX (for the LaTeX-related tools)
* Weights & Biases account (for W&B integration)
* Kubernetes access (for Kubernetes tools) 