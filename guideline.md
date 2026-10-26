# Conductor Universal Guidelines

Conductor is a general-purpose, event-driven plugin kernel. It is not tied to a
specific application domain. Plugins provide commands, events, HTTP APIs,
storage, or React pages; the kernel owns lifecycle, permissions, logging and
dependency coordination.

## Runtime model

`python -m conductor` creates a `Kernel`, starts logging, discovers plugins,
resolves dependencies, registers resources, and starts Flask plus the local CLI.
The React application consumes the API and generated plugin route manifest.

Core responsibilities:

- `Kernel`: events, commands, permissions, users, logging and shutdown.
- `PluginManager`: discovery, ordering, lifecycle and web assets.
- `conductor.interface.api`: authentication, users, status and content intake.
- `conductor.core.system_api`: core management and terminal APIs.
- `WebApp`: login, navigation, core pages and plugin pages.

Core management APIs live under `/api/core`; they do not depend on a management
plugin being loaded.

## Plugin contract

A plugin is a module or package under `conductor/plugins` or
`conductor/plugins/core`. It declares `PLUGIN_METADATA` and may define
`on_load(kernel, previous_module)` and `on_unload(kernel)`.

Use the kernel for shared services:

- `kernel.register_event_listener(...)`
- `kernel.register_command(...)`
- `kernel.register_blueprint(...)`
- `kernel.get_logger(plugin_id)`
- `kernel.get_plugin_config_dir(plugin_id)`
- `kernel.get_plugin_data_dir(plugin_id)`

Configuration belongs in `storage/config/<plugin_id>` and mutable data in
`storage/data/<plugin_id>`. Runtime storage is never committed.

## Permissions and APIs

Requests use `Authorization: Bearer <token>` or `X-Conductor-Token`.

- Public: login and health/status endpoints.
- USER: authenticated content intake and normal commands.
- ADMIN: plugin inspection, dependency operations, logs and administrative commands.
- OWNER: user management, file editing and high-risk operations.

Core APIs return `{success, data}` on success and
`{success: false, errorCode, errorMessage}` on failure. New plugins should use
the same response shape and `conductor.core.auth` helpers.

## Frontend rules

Core pages use fixed routes such as `/core/plugin-management` and `/core/terminal`.
Plugin pages are served from each plugin's `web/` directory and mounted at a
top-level route for core plugins or `/plugins/<id>` for regular plugins.

Do not treat `WebApp/src/plugin_routes.ts` as a hand-maintained source of truth:
PluginManager regenerates it at backend startup and inserts the fixed core routes.

## Dependencies

Poetry manages Python dependencies and Yarn manages WebApp dependencies. Plugin
`requirements.txt` and `web/package.json` declarations are discovered by
`scripts/sync_plugin_dependencies.py`.

```bash
python scripts/sync_plugin_dependencies.py --ecosystem all --install
poetry install
cd WebApp && yarn install
```

Use Python 3.11 or 3.12 and a current LTS Node.js release. Runtime installation
can be disabled with `CONDUCTOR_AUTO_INSTALL_PLUGIN_DEPS=0`.

## Code style and checks

Use PEP 8, type hints in core code, focused docstrings, functional React
components and explicit API errors. Keep business logic in plugins and generic
lifecycle/security logic in core.

```bash
python -m compileall conductor tests
python -m pytest -q
cd WebApp && yarn build
```

Correct plugin boundaries, authentication and a clean clone-to-run setup take
precedence over domain-specific functionality.
