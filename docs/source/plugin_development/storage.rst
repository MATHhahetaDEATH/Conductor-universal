Plugin Storage
==============

Conductor separates plugin code from runtime data so plugin updates do not overwrite user configuration or local state.

Directories
-----------

Plugin storage lives under the kernel storage root:

* ``storage/config/<plugin_id>/`` for configuration files such as JSON, YAML, or TOML.
* ``storage/data/<plugin_id>/`` for databases, downloaded assets, caches, and other runtime data.

Using the API
-------------

Do not hardcode storage paths. Resolve them through the kernel:

.. code-block:: python

    import json
    import os

    PLUGIN_METADATA = {
        "id": "my_plugin",
        "name": "Example",
    }

    def on_load(kernel, prev_module):
        config_dir = kernel.get_plugin_config_dir("my_plugin")
        data_dir = kernel.get_plugin_data_dir("my_plugin")

        config_path = os.path.join(config_dir, "config.json")
        config = {"enabled": True, "threshold": 10}

        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config.update(json.load(f))

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

Backup and restore
------------------

Back up the root ``storage/`` directory to preserve plugin configuration and data. Restoring that directory restores plugin state on the next kernel startup.

