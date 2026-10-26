Plugin Web UI Integration
=========================

Conductor integrates plugin web interfaces into the central WebApp during plugin loading. A plugin web page must be declared in ``PLUGIN_METADATA`` and its assets must live under the plugin-specific ``web/`` directory.

Loading modes
-------------

The ``PluginManager`` detects the entry file in ``<plugin>/web/``:

* **Native React mode**: ``web/index.tsx`` is linked into ``WebApp/src/pages/plugins/<plugin_id>/index.tsx`` and loaded as a WebApp route.
* **Standalone HTML portal mode**: ``web/index.html`` is served from the plugin source directory through ``/api/static/plugins/<plugin_id>/index.html``. Plugin Center's **Portal** action opens this URL directly.
* **Core terminal mode**: terminal-style command access is provided by the kernel at ``/core/terminal``.

Route tiers
-----------

Routes are assigned by plugin location and role:

* **Core plugins** live in ``conductor/plugins/core/`` and receive top-level routes, such as ``/dashboard`` or ``/prime_backup``. The fixed Core Plugin Management page is available at ``/core/plugin-management``.
* **General plugins** live directly under ``conductor/plugins/`` and receive ``/plugins/<plugin_id>`` native React routes grouped under the Conductor plugins menu. Their standalone HTML portal, when present, is opened from Plugin Center rather than from the sidebar. The group itself has a menu icon; individual non-core plugins do not need ``web_icon``.
* Core plugin terminal buttons link to ``/core/terminal``. General plugin actions are managed from the Core Plugin Management page.

Metadata fields
---------------

Register web behavior in ``PLUGIN_METADATA``:

.. code-block:: python

    PLUGIN_METADATA = {
        "id": "my_plugin",
        "version": "1.1.0",
        "name": "Custom UI Plugin",
        "web_name": "My Plugin UI",
        "web_hide_in_menu": False,
        "priority": 500,
        "dependencies": [],
    }

``web_name`` controls the menu label. ``web_hide_in_menu`` keeps an otherwise routable page out of the sidebar. General, non-core plugins do not need ``web_icon``; core plugins should provide one for their top-level menu item.

Extra web routes
----------------

Core infrastructure plugins can expose additional routes through metadata:

.. code-block:: python

    PLUGIN_METADATA = {
        "id": "example_plugin",
        "web_hide_in_menu": True,
        "web_extra_routes": [
            {
                "path": "/core/terminal",
                "name": "Terminal",
                "hideInMenu": True,
                "component": "core/web-terminal",
            }
        ],
    }

Only register extra routes that are backed by assets in the plugin's own ``web/`` directory or by a component symlinked from that directory.
