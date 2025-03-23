Core API
========

The Core API provides the foundational classes and utilities used throughout the ML Research Tools package.

Base Tool
---------

.. py:class:: ml_research_tools.core.base_tool.BaseTool

   The base class that all tools in the ML Research Tools package inherit from.

   .. py:attribute:: name
      :type: str

      The command name used to invoke the tool from the command line.

   .. py:attribute:: description
      :type: str

      A short description of the tool's functionality.

   .. py:method:: add_arguments(parser)
      :staticmethod:

      Adds tool-specific arguments to the argument parser.

      :param parser: The argument parser to add arguments to
      :type parser: argparse.ArgumentParser

   .. py:method:: execute(config, args)

      Executes the tool with the provided configuration and arguments.

      :param config: The global configuration object
      :type config: ml_research_tools.core.config.Config
      :param args: The parsed command-line arguments
      :type args: argparse.Namespace
      :return: An exit code (0 for success)
      :rtype: int

Configuration
------------

.. py:class:: ml_research_tools.core.config.Config

   Manages the configuration for the ML Research Tools, with support for loading from
   files, environment variables, and command-line arguments.

   .. py:method:: __init__(config_file=None, **kwargs)

      Initialize the configuration with optional config file and override values.

      :param config_file: Path to a YAML configuration file
      :type config_file: str, optional
      :param kwargs: Configuration overrides
      :type kwargs: dict

   .. py:method:: from_file(config_file)
      :classmethod:

      Load configuration from a YAML file.

      :param config_file: Path to the configuration file
      :type config_file: str
      :return: A new Config instance
      :rtype: Config

   .. py:method:: to_file(config_file)

      Save the current configuration to a YAML file.

      :param config_file: Path to save the configuration to
      :type config_file: str

Logging
-------

.. py:module:: ml_research_tools.core.logging_tools

   The logging_tools module provides utilities for setting up and configuring logging
   throughout the ML Research Tools.

   .. py:function:: setup_logging(level=logging.INFO, log_file=None, force=False)

      Configure the logging system with the specified level and optional file output.

      :param level: The logging level to use
      :type level: int
      :param log_file: Path to a log file to write logs to
      :type log_file: str, optional
      :param force: Force reconfiguration even if already configured
      :type force: bool
