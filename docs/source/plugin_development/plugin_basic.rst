Conductor Plugin Development
============================

What is a Conductor plugin
--------------------------

A Conductor plugin is a single ``.py`` file or a directory package placed in a configured plugin directory. Plugins extend the kernel by registering commands, event listeners, storage, API routes, and optional Web UI assets.

At startup, the Conductor kernel discovers plugins, reads ``PLUGIN_METADATA``, resolves dependencies, calls ``on_load(kernel, prev_module)``, and then deploys any registered web assets.

Quick start
-----------

Create a plugin file or a directory with an ``__init__.py`` entrypoint:

.. code-block:: python

    PLUGIN_METADATA = {
        "id": "hello_world",
        "version": "1.0.0",
        "name": "Hello World",
    }

    def on_load(kernel, prev_module):
        kernel.logger.info("Hello world! Conductor is ready.")

Metadata
--------

``PLUGIN_METADATA`` is the plugin's discovery contract. The common fields are:

.. code-block:: python

    PLUGIN_METADATA = {
        "id": "example_plugin",
        "version": "1.0.0",
        "name": "Example Plugin",
        "description": "Example plugin for Conductor",
        "author": "Developer",
        "priority": 100,
        "dependencies": ["other_plugin"],
    }

Use ``dependencies`` for plugin IDs that must load first. Use ``priority`` to order otherwise independent plugins; higher values load earlier.

Entrypoint
----------

For a single-file plugin, the entrypoint is the file itself. For a directory plugin, the entrypoint is ``__init__.py``. The entrypoint may define:

* ``PLUGIN_METADATA`` for discovery.
* ``on_load(kernel, prev_module)`` for initialization.
* ``on_unload(kernel)`` for cleanup.
* Event listener decorators and command registration code.

Development topics
------------------

The plugin development guide is split by responsibility:

* :doc:`plugin_web` describes native React, iframe, and Web CLI bridge pages.
* :doc:`commands` describes command trees and command registration.
* :doc:`events` describes lifecycle and custom event listeners.
* :doc:`storage` describes config/data directories for persistent plugin state.
* :doc:`permissions` describes permission levels for plugin commands and API-facing execution.

Minimal plugin layout
---------------------

.. code-block:: text

    conductor/plugins/my_plugin/
    ├── __init__.py
    └── web/
        └── index.tsx

Keep plugin-specific code, web assets, and static pages under the plugin's own directory. Runtime config and data should use the storage helpers rather than files inside the plugin source tree.

