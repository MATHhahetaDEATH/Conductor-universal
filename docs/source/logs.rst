Unified Logs
============

Conductor uses one logging interface for kernel code, plugins, web APIs, realtime viewers, and saved log files.

Format
------

Every visible and stored log line uses the same format:

.. code-block:: text

    [YYYY-MM-DD HH:MM:SS] [logger.name/LEVEL]: message

Examples:

.. code-block:: text

    [2026-04-27 12:07:02] [conductor.plugins/INFO]: Updated WebApp route manifest with 8 routes.
    [2026-04-27 12:07:01] [conductor.plugins.hello_world/INFO]: Initializing Hello World Plugin with Storage support...

Startup Sessions
----------------

Logs are split by process startup. Each run creates a new directory:

.. code-block:: text

    storage/logs/<YYYYMMDD-HHMMSS>/
    |- core/core.log
    |- plugin/<plugin_id>.log
    `- web/frontend.log

Realtime log APIs and Web UI views show records from the current startup session only. Saved files contain the exact same lines shown in realtime views.

Plugin Logging
--------------

Plugins should use the kernel logger interface:

.. code-block:: python

    def on_load(kernel, prev_module):
        logger = kernel.get_logger("my_plugin")
        logger.info("Plugin started")
        logger.warning("Configuration is using a default value")
        logger.error("Something failed")

During ``on_load``, ``kernel.logger`` is also temporarily scoped to the loading plugin. For long-lived callbacks, prefer ``kernel.get_logger(plugin_id)``.

Levels
------

Supported levels are standard Python logging levels:

* ``DEBUG``
* ``INFO``
* ``WARNING``
* ``ERROR``
* ``CRITICAL``

The root level can be changed at runtime:

.. code-block:: text

    !!conductor logs status
    !!conductor logs level DEBUG
    !!conductor logs level INFO
    !!conductor logs retention size 512
    !!conductor logs retention age 14
    !!conductor logs retention size 512 age 14

Retention Policy
----------------

The built-in log service stores its settings in ``storage/config/log_manager/config.json``:

.. code-block:: json

    {
      "level": "INFO",
      "max_total_mb": 512,
      "max_age_days": 14
    }

``max_total_mb`` limits the total size of completed startup sessions. ``max_age_days`` removes completed sessions older than the configured age. The current startup session is never deleted while the process is running.

Built-in Log Service
--------------------

Conductor provides the following log features as a built-in system service:

* A top-level ``Logs`` web page.
* Realtime filtering by category, owner, and level.
* Current-session log file download.
* Runtime root log-level settings.
* Retention settings for maximum total storage and maximum session age.

API
---

``GET /api/logs/settings``
    Returns the current session ID, session directory, and root level.

``POST /api/logs/settings``
    Updates settings. Supports ``{"level": "INFO", "max_total_mb": 512, "max_age_days": 14}``.

``GET /api/logs/records``
    Returns current-session records. Query parameters: ``category``, ``owner``, ``levels``, ``limit``.

``GET /api/logs/files``
    Lists current-session log files.

``GET /api/logs/download?category=plugin&owner=hello_world``
    Downloads one current-session log file.

``POST /api/logs/web``
    Accepts frontend/web log messages and stores them under ``web/frontend.log``.
