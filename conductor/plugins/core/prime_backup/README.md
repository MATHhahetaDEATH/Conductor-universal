# Prime Backup

Native deduplicated backup and restore service.

- Route: `/prime_backup`
- API: `/api/prime_backup/status`, `/list`, `/make`, `/restore`, `/delete`
- Configuration: `storage/config/prime_backup/config.json`
- Data: plugin SQLite metadata plus configured backup storage
- Permissions: authenticated reads; ADMIN for create/restore/delete.

Backup paths are local runtime state and are excluded from Git.
