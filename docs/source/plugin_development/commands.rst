Plugin Commands
===============

Conductor's command tree lets plugins define structured commands for data processing, system management, and inspection.

Workflow
--------

The kernel maintains a command registry. When input arrives from the CLI, REST API, or Web CLI bridge, the kernel parses it against registered command trees, fills a context dictionary, and calls the matching callback.

Command structure
-----------------

Commands are built from nodes. For example:

* ``!!process analyze <source_id>``
* ``!!process status <job_id>``
* ``!!process filter <source_id> --threshold <value>``

The command tree shape is:

.. code-block:: text

    Literal("!!process")
     |- Literal("analyze")
     |  `- Text("source_id")
     |- Literal("status")
     |  `- Integer("job_id")
     `- Literal("filter")
        `- Text("source_id")
           `- Float("threshold")

SimpleCommandBuilder
--------------------

Use ``SimpleCommandBuilder`` for related commands:

.. code-block:: python

    from conductor.core.command.builder import SimpleCommandBuilder
    from conductor.core.command.node import Integer, Text

    def on_load(kernel, prev_module):
        builder = SimpleCommandBuilder()
        builder.command("!!process analyze <source_id>", analyze_source, plugin_id="my_plugin")
        builder.command("!!process status <job_id>", get_status, plugin_id="my_plugin")
        builder.arg("source_id", Text)
        builder.arg("job_id", Integer)
        builder.register(kernel)

High-level registration
-----------------------

For simple commands, use ``kernel.register_command``:

.. code-block:: python

    from conductor.core.permission import PermissionLevel

    def on_load(kernel, prev_module):
        kernel.register_command(
            "!!hello <name>",
            callback=say_hello,
            permission=PermissionLevel.USER,
            description="Say hello",
            plugin_id="my_plugin",
        )

Callbacks
---------

Callbacks receive ``source`` and ``context``:

.. code-block:: python

    def analyze_source(source, context):
        source.reply(f"Starting analysis for {context['source_id']}...")

See :doc:`permissions` for command permission levels.

