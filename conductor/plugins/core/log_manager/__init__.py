from __future__ import annotations


PLUGIN_METADATA = {
    "id": "log_manager",
    "version": "1.0.0",
    "name": "Log Manager",
    "description": "Unified realtime log viewer.",
    "author": "kasumitang",
    "priority": 950,
    "web_name": "Logs",
    "web_icon": "storage",
}


def on_load(kernel, prev_module):
    kernel.logger.info("Log Manager web plugin loaded.")
