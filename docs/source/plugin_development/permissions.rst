Plugin Permissions
==================

Conductor uses permission levels to protect commands exposed through CLI, REST API, and Web CLI bridge execution.

Levels
------

.. list-table::
   :header-rows: 1

   * - Name
     - Value
     - Typical use
   * - ``OWNER``
     - 4
     - Physical terminal or trusted owner-level integrations.
   * - ``ADMIN``
     - 3
     - Plugin management and privileged system operations.
   * - ``HELPER``
     - 2
     - Trusted automation or subsystem helpers.
   * - ``USER``
     - 1
     - Standard API and web-facing operations.
   * - ``GUEST``
     - 0
     - Restricted or unauthenticated access.

Assigning permissions
---------------------

Set the minimum level when registering a command:

.. code-block:: python

    from conductor.core.permission import PermissionLevel

    def on_load(kernel, prev_module):
        kernel.register_command(
            "!!admin_only",
            my_callback,
            PermissionLevel.ADMIN,
            "Sensitive operation",
            plugin_id="my_plugin",
        )

Web CLI bridge
--------------

Core Web Terminal executes commands through the authenticated user's permission level.
