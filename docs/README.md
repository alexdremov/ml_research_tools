# ML Research Tools Documentation

This directory contains the documentation for the ML Research Tools package.

## Building the Documentation

To build the documentation locally:

1. Install the package with documentation dependencies:
   ```bash
   poetry install --with docs
   ```

2. Build the HTML documentation:
   ```bash
   cd docs
   poetry run make html
   ```

3. Open the built documentation:
   ```bash
   open build/html/index.html  # On macOS
   # Or
   xdg-open build/html/index.html  # On Linux
   ```

## Documentation Structure

- `source/`: Contains the documentation source files
  - `conf.py`: Sphinx configuration
  - `index.rst`: Main documentation entry point
  - `api/`: API reference documentation
  - `tools/`: Tool-specific documentation

## Deployed Documentation

The documentation is automatically built and deployed to GitHub Pages when changes are pushed to the main branch.

The latest version of the documentation can be accessed at: https://alexdremov.github.io/ml_research_tools/ 