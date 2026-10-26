
Built-in Commands
=================

Conductor provides a set of built-in commands under the ``!!conductor`` namespace to manage the kernel, plugins, and permissions. These commands are modeled after the MCDR command system.

Primary Commands
----------------

!!conductor
^^^^^^^^^^^

The base command for system management.

-   **Usage**: ``!!conductor <subcommand> [args...]``
-   **Permission**: ``GUEST`` (Base command depends on subcommands)

!!help
^^^^^^

A shortcut to display all available commands.

-   **Alias**: ``!!conductor help``
-   **Permission**: ``GUEST``

Management Sub-commands
-----------------------

status
^^^^^^

Displays the current state of the Conductor kernel.

-   **Command**: ``!!conductor status``
-   **Permission**: ``USER``
-   **Details**: Shows version, uptime, and loaded plugin count. Owners can also see the Process ID (PID).

reload
^^^^^^

Hot-reload system components or plugins.

-   **Command**: ``!!conductor reload <plugin|all>``
-   **Short form**: ``!!conductor r <plugin|all>``
-   **Permission**: ``ADMIN``

plugin
^^^^^^

Manage individual plugins.

-   **Command group**: ``!!conductor plugin <list|info|load|reload|unload|reloadall>``
-   **Short form**: ``!!conductor plg ...``
-   **Permission**: ``ADMIN``

-   ``list``: Lists all loaded plugins.
-   ``info <plugin_id>``: Displays detailed metadata for a plugin.
-   ``load <file_name>``: Loads a new plugin file from the plugin directories.
-   ``unload <plugin_id>``: Gracefully unloads a plugin and removes its listeners.
-   ``reload <plugin_id>``: Reloads the plugin and every loaded plugin that directly or indirectly depends on it, preserving dependency order.
-   ``reloadall``: Reloads all currently loaded plugins.

permission
^^^^^^^^^^

Query and manage permissions.

-   **Command group**: ``!!conductor permission <query>``
-   **Short form**: ``!!conductor perm ...``
-   **Permission**: ``USER``

-   ``query [<player>]``: Returns the current permission level of the sender or a specified user (if implemented).

debug
^^^^^

Utilities for developers to inspect the kernel state.

-   **Command group**: ``!!conductor debug <command_dump>``
-   **Permission**: ``ADMIN``

-   ``command_dump [plugin <plugin_id>]``: Prints a list of all registered command triggers and their originating plugins.

When the process runs with ``CONDUCTOR_DEBUG=1`` or ``FLASK_DEBUG=1``, Conductor also starts a lightweight plugin watcher. It monitors plugin ``.py``, ``.tsx``, ``.ts``, ``.html``, ``.css``, ``.less``, and ``.json`` files and reloads the changed plugin automatically. The watcher also rewrites the generated WebApp plugin route manifest after reloads so menu routes stay in sync.
