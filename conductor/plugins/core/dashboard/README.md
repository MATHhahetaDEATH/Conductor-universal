# Dashboard

Core system overview and command entry points.

- Route: `/dashboard`
- API: `/api/dashboard/status`
- Commands: `!!status`, `!!conductor status`, `!!help`, `!!conductor help`, `!!stop`
- Storage: none
- Permissions: status/help are user or guest; shutdown requires ADMIN.

The dashboard is intentionally small. Generic plugin administration belongs to
the kernel Core Plugin Management page.
