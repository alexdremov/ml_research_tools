Weights & Biases Downloader Tool
============================

The Weights & Biases (W&B) Downloader Tool helps download run logs from W&B to local JSON files.

Description
----------

This tool allows you to download run logs and metadata from Weights & Biases projects.
It saves run data to JSON files in a structured directory format, making it easier to process
W&B experiment data offline or archive results.

Usage
-----

.. code-block:: bash

    ml_research_tools wandb-downloader [options]

.. program-output:: ml_research_tools wandb-downloader --help

Examples
--------

Download all runs from a project:

.. code-block:: bash

    ml_research_tools wandb-downloader --entity myuser --project myproject

Custom output directory:

.. code-block:: bash

    ml_research_tools wandb-downloader -e myuser -p myproject -o ./experiment_logs

Using environment variables:

.. code-block:: bash

    export WANDB_ENTITY=myuser
    export WANDB_PROJECT=myproject
    ml_research_tools wandb-downloader

Output Structure
---------------

Downloaded logs are organized in the following structure:

.. code-block:: text

    output_dir/
    ├── run_id_1/
    │   ├── config.json
    │   ├── summary.json
    │   └── history.json
    ├── run_id_2/
    │   ├── config.json
    │   ├── summary.json
    │   └── history.json
    └── ...

Requirements
-----------

This tool requires the Weights & Biases Python package:

.. code-block:: bash

    pip install wandb
