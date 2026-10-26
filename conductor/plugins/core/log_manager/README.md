# Log Manager

Provides the current-session log viewer backed by the kernel logging service.

- Route: `/log_manager`
- API: `/api/logs/*`
- Configuration: `storage/config/log_manager/config.json`
- Data: `storage/logs/`
- Permissions: authenticated read; ADMIN for settings and retention changes.

The plugin metadata keeps the WebApp entry point while log lifecycle and storage
are owned by `SystemLogService` in the kernel.
