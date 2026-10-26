from __future__ import annotations

import os
from functools import wraps
from pathlib import Path

from flask import Blueprint, jsonify, request

from .auth import require_admin
from .permission import PermissionLevel


core_management_bp = Blueprint("core_management", __name__)


def _plugin_rows(kernel):
    kernel.dependencies.scan_plugin_dirs()
    records = kernel.dependencies.get_plugin_records()
    loaded = set(kernel.plugins.loaded_plugins)
    rows = []
    for pid, record in records.items():
        meta = record.get("metadata", {})
        path = record.get("path", "")
        web = Path(path) / "web"
        rows.append({
            "id": pid, "name": meta.get("name", pid), "version": meta.get("version", "unknown"),
            "author": meta.get("author", "Unknown"), "description": meta.get("description", ""),
            "priority": meta.get("priority", 0), "dependencies": meta.get("dependencies", []),
            "status": "loaded" if pid in loaded else "stopped", "is_core": bool(record.get("is_core")),
            "has_web_portal": (web / "index.html").is_file(),
            "web_portal_url": f"/api/static/plugins/{pid}/index.html" if (web / "index.html").is_file() else None,
            "entry": record.get("entry"),
        })
    return rows


def _safe_file(kernel, pid: str, category: str, name: str, write: bool = False) -> Path:
    if category not in {"config", "data"}:
        raise ValueError("category must be config or data")
    base = Path(kernel.get_plugin_config_dir(pid) if category == "config" else kernel.get_plugin_data_dir(pid)).resolve()
    target = (base / name).resolve()
    if target != base and base not in target.parents:
        raise PermissionError("Invalid path")
    if write:
        target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _plugin_exists(kernel, pid: str) -> bool:
    kernel.dependencies.scan_plugin_dirs()
    return pid in kernel.dependencies.get_plugin_records()


def register_management(kernel) -> None:
    @core_management_bp.get("/plugins")
    @require_admin(kernel)
    def plugins(_user):
        return jsonify({"success": True, "data": {"plugins": _plugin_rows(kernel)}})

    @core_management_bp.post("/plugin/action")
    @require_admin(kernel)
    def action(_user):
        data = request.get_json(silent=True) or {}
        pid, operation = data.get("plugin_id"), data.get("action")
        if not pid or operation not in {"reload", "unload"}:
            return jsonify({"success": False, "errorMessage": "plugin_id and action=reload|unload are required"}), 400
        result = (kernel.plugins.reload_plugin_cascade(pid) if operation == "reload" else kernel.plugins.unload_plugin_cascade(pid))
        return jsonify({"success": bool(result.get("success")), "data": result}), 200 if result.get("success") else 400

    @core_management_bp.get("/plugin/files")
    @require_admin(kernel)
    def files(_user):
        pid = request.args.get("id")
        if not pid:
            return jsonify({"success": False, "errorMessage": "id is required"}), 400
        if not _plugin_exists(kernel, pid):
            return jsonify({"success": False, "errorMessage": "Plugin not found"}), 404
        result = []
        for category, directory in (("config", kernel.get_plugin_config_dir(pid)), ("data", kernel.get_plugin_data_dir(pid))):
            result.extend({"name": item.name, "category": category} for item in Path(directory).iterdir() if item.is_file())
        return jsonify({"success": True, "data": {"files": result}})

    @core_management_bp.route("/plugin/file", methods=["GET", "POST"])
    @require_admin(kernel)
    def file(user):
        data = request.args if request.method == "GET" else (request.get_json(silent=True) or {})
        pid, name, category = data.get("id"), data.get("name"), data.get("category")
        if not all((pid, name, category)):
            return jsonify({"success": False, "errorMessage": "id, name and category are required"}), 400
        if not _plugin_exists(kernel, pid):
            return jsonify({"success": False, "errorMessage": "Plugin not found"}), 404
        try:
            target = _safe_file(kernel, pid, category, name, write=request.method == "POST")
        except (ValueError, PermissionError) as exc:
            return jsonify({"success": False, "errorMessage": str(exc)}), 403
        if request.method == "GET":
            if not target.is_file():
                return jsonify({"success": False, "errorMessage": "File not found"}), 404
            return jsonify({"success": True, "data": {"content": target.read_text(encoding="utf-8")}})
        if int(user.get("permission_level", 0)) < int(PermissionLevel.OWNER):
            return jsonify({"success": False, "errorCode": "AUTH_ERROR", "errorMessage": "Owner permission required"}), 403
        target.write_text(str(data.get("content", "")), encoding="utf-8")
        return jsonify({"success": True})

    @core_management_bp.get("/plugin/logs")
    @require_admin(kernel)
    def logs(_user):
        pid = request.args.get("id", "core")
        category = "core" if pid == "core" else "plugin"
        records = kernel.logs.query(category=category, owner=pid, limit=500)
        return jsonify({"success": True, "data": {"logs": [item["line"] + "\n" for item in records], "records": records}})

    @core_management_bp.get("/topology")
    @require_admin(kernel)
    def topology(_user):
        nodes = [{"id": p["id"], "name": p["metadata"].get("name", p["id"]), "is_core": p.get("is_core", False), "priority": p.get("priority", 0)} for p in kernel.plugins.plugin_candidates]
        return jsonify({"success": True, "data": {"nodes": nodes, "links": [{"source": a, "target": b} for a, b in kernel.plugins.dependency_edges]}})

    @core_management_bp.get("/dependencies")
    @require_admin(kernel)
    def dependencies(_user):
        return jsonify({"success": True, "data": kernel.dependencies.get_status()})

    @core_management_bp.post("/dependencies/sync")
    @require_admin(kernel)
    def sync(_user):
        ecosystem = (request.get_json(silent=True) or {}).get("ecosystem", "all")
        return jsonify({"success": True, "data": kernel.dependencies.sync_manifests(ecosystem)})

    @core_management_bp.post("/dependencies/install")
    @require_admin(kernel)
    def install(_user):
        ecosystem = (request.get_json(silent=True) or {}).get("ecosystem", "all")
        result = kernel.dependencies.install_missing(ecosystem)
        return jsonify({"success": result.get("success", False), "data": result})

    def inject(func):
        @wraps(func)
        def wrapper(source, ctx):
            ctx["kernel"] = kernel
            return func(source, ctx)
        return wrapper

    def cmd_list(source, ctx):
        source.reply("\n".join(f"[{p['id']}] {p['name']} (v{p['version']})" for p in _plugin_rows(kernel)) or "No plugins loaded.")

    def cmd_info(source, ctx):
        pid = ctx.get("plugin_id")
        row = next((p for p in _plugin_rows(kernel) if p["id"] == pid), None)
        source.reply(str(row) if row else f"Plugin '{pid}' not found.")

    def cmd_reload(source, ctx):
        pid = ctx.get("plugin_id")
        result = kernel.plugins.reload_plugin_cascade(pid)
        source.reply(str(result))

    def cmd_unload(source, ctx):
        pid = ctx.get("plugin_id")
        result = kernel.plugins.unload_plugin_cascade(pid)
        source.reply(str(result))

    def cmd_sync(source, ctx):
        source.reply(str(kernel.dependencies.sync_manifests((ctx.get("target") or "all").lower())))

    kernel.register_command("!!conductor plugin list", inject(cmd_list), PermissionLevel.ADMIN, "List loaded plugins", "core")
    kernel.register_command("!!conductor plugin info <plugin_id>", inject(cmd_info), PermissionLevel.ADMIN, "Show plugin metadata", "core")
    kernel.register_command("!!conductor plugin reload <plugin_id>", inject(cmd_reload), PermissionLevel.ADMIN, "Reload a plugin", "core")
    kernel.register_command("!!conductor plugin unload <plugin_id>", inject(cmd_unload), PermissionLevel.ADMIN, "Unload a plugin", "core")
    kernel.register_command("!!conductor dependencies sync <target>", inject(cmd_sync), PermissionLevel.ADMIN, "Sync plugin dependencies", "core")
