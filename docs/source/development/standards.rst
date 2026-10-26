
Development Standards
=====================

This document outlines the coding standards and development workflow for the Conductor project.

Coding Standards
----------------

*   **PEP 8**: Follow the standard Python style guide.
*   **Black**: Use ``black`` for code formatting.
*   **isort**: Use ``isort`` to organize imports alphabetically and by category.
*   **Type Hints**: Mandatory for all core logic.
*   **Docstrings**: Use **Google Style** docstrings for all public classes and methods.

Development Workflow
--------------------

We use **Poetry** for dependency management and environment isolation.

Installation
^^^^^^^^^^^^

Install the development environment with all dev dependencies:

.. code-block:: bash

    poetry install

Launching From Source
^^^^^^^^^^^^^^^^^^^^^

During development, you can launch the Conductor kernel directly from source using Poetry:

.. code-block:: bash

    poetry run python -m conductor

Enable debug mode for plugin hot reload during active development:

.. code-block:: bash

    CONDUCTOR_DEBUG=1 poetry run python -m conductor

Debug mode raises logging verbosity and watches plugin source/web files. When a watched file changes, Conductor reloads the owning plugin and rewrites the generated WebApp plugin route manifest.

Running Tests
^^^^^^^^^^^^^

We use ``pytest`` for testing. Run the test suite with:

.. code-block:: bash

    poetry run pytest

Linting and Formatting
^^^^^^^^^^^^^^^^^^^^^^

Before submitting code, ensure it aligns with our standards by running the following tools:

.. code-block:: bash

    # Format code
    poetry run black .
    poetry run isort .

    # Check types
    poetry run mypy .

Git Guidelines
--------------

*   Use descriptive commit messages.
*   Keep pull requests focused on a single feature or bug fix.
*   Include tests for any new functionality.
