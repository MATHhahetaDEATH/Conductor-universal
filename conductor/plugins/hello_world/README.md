# Hello World

Reference plugin and smoke-test target for the plugin contract.

- Route: `/plugins/hello_world`
- API: `/api/hello_world/state`
- Commands: `!!hello`, `!!hello <name>`
- Configuration: `storage/config/hello_world/config.json`
- Data: `storage/data/hello_world/state.json`
- Permissions: authenticated API; USER command access.

The plugin demonstrates configuration, mutable data, an event listener, a command,
a Blueprint and a native React page.
