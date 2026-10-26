Developer Documentation: Event System
==================================

Conductor's architecture is built on a highly decoupled event-driven model. This document describes the internal structure of the event-listener system and how callbacks are managed.

System Architecture
------------------

The event system consists of four primary components:

1.  **EventDispatcher (`conductor/core/events.py`)**: The low-level engine that manages listener registration and execution.
2.  **Kernel API (`conductor/core/kernel.py`)**: Provides the developer-facing interface for dispatching and registering events.
3.  **Plugin Manager (`conductor/core/plugin_manager.py`)**: Handles the automatic discovery and registration of listeners during plugin loading.
4.  **Listeners (Plugins)**: Where the actual **callback functions** are implemented.

Callback Definition
-------------------

Callbacks in Conductor are standard Python functions defined within **Plugins**. There are two ways they are registered:

### 1. Decorated Callbacks
Developers can use the `@event_listener` decorator to mark functions as callbacks.

.. code-block:: python

    from conductor.core.events import event_listener

    @event_listener('conductor.content_received')
    def my_callback(kernel, data):
        # Implementation of the callback
        pass

### 2. Manual Registration
Callbacks can also be registered dynamically using the kernel API.

.. code-block:: python

    def on_load(kernel, prev):
        kernel.register_event_listener('conductor.kernel_start', my_other_callback)

Internal Structure
------------------

.. mermaid::

    graph TD
        Kernel[Kernel] -- dispatch_event --> Dispatcher[EventDispatcher]
        Dispatcher -- calls --> Callback[Plugin Callback Function]
        
        PluginManager -- register --> Dispatcher
        PluginManager -- find decorators --> GlobalList[_DECORATED_LISTENERS]
        GlobalList -- imported into --> Dispatcher

The Lifecycle of an Event
-------------------------

1.  **Trigger**: An event is triggered via ``kernel.dispatch_event(event_id, *args)``.
2.  **Lookup**: The ``EventDispatcher`` looks up all callbacks registered for that ``event_id``.
3.  **Sorting**: Callbacks are sorted by their **priority** (default is 1000).
4.  **Execution**: The dispatcher iterates through the callbacks and executes them. If a callback raises an exception, it is logged, but the execution of other listeners continues.

Built-in Events
---------------

The following table summarizes the built-in events and where their dispatch calls are located:

+------------------------------+-------------------------------------+---------------------------------------+
| Event ID                     | Dispatch Source Location            | Trigger Context                       |
+==============================+=====================================+=======================================+
| ``conductor.kernel_start``   | ``conductor/core/kernel.py``        | When kernel and plugins are ready     |
+------------------------------+-------------------------------------+---------------------------------------+
| ``conductor.kernel_stop``    | ``conductor/core/kernel.py``        | Before the system shuts down          |
+------------------------------+-------------------------------------+---------------------------------------+
| ``conductor.content_received``| ``conductor/interface/api/routes.py``| When new data arrives via REST API   |
+------------------------------+-------------------------------------+---------------------------------------+

Managing Listeners
------------------

When a plugin is unloaded, the kernel automatically cleans up all associated listeners using ``kernel.remove_listeners_by_plugin(plugin_id)``. This ensures that stale callbacks do not attempt to execute after their source module is removed.

Web Application Integration
---------------------------

Conductor comes with an Ant Design Pro-based frontend (`WebApp`). In the development environment, the connection between the frontend and the Conductor kernel is established via standard HTTP REST API endpoints and a proxy configuration.

1. **Proxy Configuration**:
   The frontend runs on an independent development server (usually ``localhost:8678``). To circumvent CORS limitations and simulate a production directory structure, all requests to ``/api/*`` from the frontend are proxied to the Conductor backend at ``localhost:5678`` by configuring ``WebApp/config/proxy.ts``.

2. **Standard API Response Schema**:
   To interface flawlessly with the frontend `request` framework (based on `umi-request` and `@umijs/max`), all Conductor API responses uniformly adopt the ``success`` wrapped format:

   .. code-block:: json

       {
           "success": true,
           "data": {
               "status": "...",
               "plugins": []
           },
           "errorCode": "OPTIONAL_ERROR_CODE",
           "errorMessage": "Description on failure"
       }

3. **Frontend Services**:
   The API mappings are explicitly defined within TypeScript services in the WebApp. For the Conductor core backend endpoints, refer to ``WebApp/src/services/conductor.ts``.
