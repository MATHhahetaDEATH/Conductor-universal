Plugin Events
=============

Plugin events let plugins react to kernel lifecycle changes, content flows, and custom inter-plugin messages.

Priority
--------

Event listeners have a priority value. Lower values run first. Use priority when several plugins must react in a deterministic order.

Registration
------------

Plugins can register listeners through conventional entrypoint functions, direct kernel registration, or the event decorator API.

.. code-block:: python

    def on_load(kernel, prev_module):
        kernel.logger.info("Plugin initialized")

    def register_more(kernel):
        kernel.register_event_listener("my_plugin.task_finished", handle_task_finished)

Lifecycle events
----------------

``conductor.plugin_loaded``
    Called through ``on_load(kernel, prev_module)`` when a plugin is initialized.

``conductor.plugin_unloaded``
    Called through ``on_unload(kernel)`` when a plugin unloads or the system shuts down.

``conductor.kernel_start``
    Emitted after kernel initialization.

``conductor.kernel_stop``
    Emitted during shutdown. Use it for cleanup.

Custom events
-------------

Plugins can dispatch custom events for inter-plugin coordination:

.. code-block:: python

    kernel.dispatch_event("my_plugin.task_finished", task_id)

Listeners should keep event IDs namespaced by plugin ID to avoid collisions.

