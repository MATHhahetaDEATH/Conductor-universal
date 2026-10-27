Dependency Management
=====================

Conductor has two dependency layers:

* Backend Python dependencies for the kernel and plugin runtime.
* Frontend WebApp dependencies for React plugin pages.

The dependency manager discovers plugin dependency declarations, syncs them into the project manifests, checks the local environment, and tracks which plugins reference each dependency. Python dependencies are registered in the root ``pyproject.toml``. React dependencies are registered in ``WebApp/package.json``.

Plugin Declarations
-------------------

Python plugins may declare backend dependencies with a plugin-local ``requirements.txt``:

.. code-block:: text

    requests>=2.32
    beautifulsoup4

Native React plugin pages may declare frontend dependencies with ``web/package.json``:

.. code-block:: json

    {
      "dependencies": {
        "@monaco-editor/react": "^4.7.0"
      },
      "peerDependencies": {
        "react": "^17.0.0"
      }
    }

Conductor scans these files directly from the plugin directories, maps them back to the plugin entry's ``PLUGIN_METADATA``/``METADATA`` declaration, records dependency ownership by plugin ID, and synchronizes missing declarations into the project manifests. This scan does not require the plugin to import successfully, so missing runtime packages can still be surfaced and synced.

Status and Reference Counting
-----------------------------

The dependency manager reports:

* ecosystem: ``python`` or ``web``.
* package name and requested specifiers.
* installed version when found.
* status: ``ok``, ``missing``, or ``version_mismatch``.
* plugins that reference the package.

When a plugin unloads, its dependency references are removed from the current graph. A dependency should only be removed from the environment when no loaded plugin references it and it is not a core project dependency.

Reload Chains
-------------

Plugin reloads are dependency- and priority-aware. Conductor first computes the canonical loaded order from plugin dependencies, priority, core status, and plugin ID, then reloads the selected plugin plus every loaded plugin after it in that order. It unloads the chain from downstream to upstream, then loads it again from upstream to downstream.

Reloading a high-priority core plugin also reloads lower-priority plugins that are later in the canonical order. This prevents downstream plugins from keeping stale Python objects, command registrations, routes, or dependency state from the old upstream instance.

Plugin Center
-------------

Core Plugin Management includes a **Dependencies** section. It shows dependency
status in a table with ecosystem, declared and installed versions, status,
referring plugins, and source manifests. Ecosystem filtering and a text filter
help narrow the list. The section also offers manifest sync and explicit missing
dependency installation actions. Each row shows which plugin declared the
dependency.

After manifests are synchronized, the normal project tools complete the installation:

.. code-block:: bash

    poetry install
    cd WebApp && yarn install

When the backend starts through ``poetry run python -m conductor``, Conductor synchronizes plugin Python declarations before plugin initialization and, unless ``CONDUCTOR_AUTO_INSTALL_PLUGIN_DEPS=0`` is set, runs ``poetry install`` if plugin Python packages are missing. ``WebApp`` runs ``scripts/sync_plugin_dependencies.py --ecosystem web --install`` before ``yarn dev``, ``yarn start``, and ``yarn build``.

Production images should still bake dependencies into the image and commit intentional lockfile updates.

Docker Standard
---------------

For production, dependencies should be baked into the image rather than installed at runtime.

Recommended build flow:

1. Collect backend dependencies from the root ``pyproject.toml`` and plugin ``requirements.txt`` files.
2. Add approved backend dependencies to ``pyproject.toml`` and update ``poetry.lock``.
3. Collect frontend dependencies from ``WebApp/package.json`` and plugin ``web/package.json`` files.
4. Add approved frontend dependencies to ``WebApp/package.json`` and update ``WebApp/yarn.lock``.
5. Build the WebApp in a Node build stage.
6. Install Python dependencies with Poetry in the Python runtime stage.
7. Copy built frontend assets and the ``conductor`` package into the final image.

Runtime containers should mount only storage/config/data volumes. Avoid mounting ``.venv`` or ``WebApp/node_modules`` into production containers; those directories are machine-specific build artifacts.

Development Standard
--------------------

For local development:

* Python dependencies live in Poetry's virtualenv, commonly ``.venv`` when configured locally.
* React dependencies live in ``WebApp/node_modules``.
* Plugin dependency changes are synchronized into ``pyproject.toml`` and ``WebApp/package.json``.
* Lock files should be reviewed before being committed or baked into Docker.
* Set ``CONDUCTOR_AUTO_INSTALL_PLUGIN_DEPS=0`` to disable backend startup installs while keeping manifest synchronization.
* Plugin WebApp pages are exposed in ``WebApp/src/pages/plugins`` via regenerated symlinks during load/reload so the frontend dev server can observe plugin refreshes without copying plugin sources into the frontend tree.

API
---

``GET /api/core/dependencies``
    Returns current dependency status, plugin ownership, next manifest-update actions, and manifest sync preview.

``POST /api/core/dependencies/sync``
    Synchronizes plugin dependencies into project manifests. Body: ``{"ecosystem": "all"}``, ``{"ecosystem": "python"}``, or ``{"ecosystem": "web"}``.

``POST /api/core/dependencies/install``
    Legacy explicit runtime installer. Prefer manifest sync plus ``poetry install`` / ``yarn install``.
