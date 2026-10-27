Core Plugin Management
======================

The WebApp page at ``/core/plugin-management`` provides the administrative view
of discovered and loaded plugins. Core management APIs require an authenticated
administrator. Saving a plugin config or data file requires Owner permission.

Plugins
-------

The first table lists each plugin's ID, name, version, load state, type, and
whether it exposes a web portal. Selecting a row opens plugin details:

* **Lifecycle** reloads or unloads a plugin. Reload uses the runtime's dependency
  cascade so downstream plugins can be reinitialized in order.
* **Files** lists plugin config and data files, displays their contents, and
  permits an Owner to save changes.
* **Logs** displays the most recent log records associated with the plugin.
* **Portal** opens ``web/index.html`` when the plugin provides one.

Dependencies
------------

The Dependencies section displays package name, ecosystem, declared specifiers,
installed version, status, referring plugins, and manifest sources in a table.
Use the ecosystem selector and filter to narrow the rows. **Sync manifests**
updates the project manifests; **Install missing** invokes the explicit runtime
installer. After syncing, normal project installation is preferred (``poetry
install`` for Python and ``yarn install`` in ``WebApp/`` for web packages).

Topology
--------

The Topology section renders plugin candidates as an interactive directed graph.
Core and regular plugins use separate colors; arrows show dependency direction.
Nodes can be dragged, the graph can be zoomed and fitted to its contents, and
clicking a plugin node opens its details.

Management API
--------------

The page uses these authenticated endpoints under ``/api/core``:

* ``GET /plugins``
* ``POST /plugin/action`` with ``plugin_id`` and ``action`` (``reload`` or
  ``unload``)
* ``GET /plugin/files?id=<plugin_id>``
* ``GET|POST /plugin/file`` with ``id``, ``name``, and ``category``
* ``GET /plugin/logs?id=<plugin_id>``
* ``GET /dependencies``
* ``POST /dependencies/sync`` and ``POST /dependencies/install``
* ``GET /topology``

File categories are limited to ``config`` and ``data``. File paths are confined
to the selected plugin's storage directory.
