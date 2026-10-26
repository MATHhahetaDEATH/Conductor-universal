from __future__ import annotations

import json
import logging
import os

from flask import Blueprint, Response, jsonify, request

from conductor.core.command.builder import SimpleCommandBuilder
from conductor.core.command.node import Integer, Text
from conductor.core.permission import PermissionLevel
from conductor.core.auth import current_user, error


DEFAULT_CONFIG = {
    "level": "INFO",
    "max_total_mb": 512,
    "max_age_days": 14,
}


class SystemLogService:
    """Kernel-owned log configuration, API, and commands."""

    def __init__(self, kernel) -> None:
        self.kernel = kernel
        self.config_path = os.path.join(kernel.get_plugin_config_dir("log_manager"), "config.json")
        self.blueprint = Blueprint("system_logs", __name__)
        self._register_routes()

    def register(self) -> None:
        config = self.load_config()
        self.apply_config(config)
        self.save_config(config)
        self.kernel.register_blueprint(self.blueprint, url_prefix="/api/logs")
        self._register_commands()
        self.kernel.logger.info("System log service registered.")

    def load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            return dict(DEFAULT_CONFIG)
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            return dict(DEFAULT_CONFIG)

    def save_config(self, config: dict) -> None:
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def apply_config(self, config: dict) -> dict:
        if config.get("level"):
            self.kernel.logs.set_level(config["level"])
        return self.kernel.logs.prune_sessions(
            max_total_mb=int(config.get("max_total_mb", DEFAULT_CONFIG["max_total_mb"])),
            max_age_days=int(config.get("max_age_days", DEFAULT_CONFIG["max_age_days"])),
        )

    def _register_routes(self) -> None:
        @self.blueprint.before_request
        def require_log_access():
            user = current_user(self.kernel)
            if not user:
                return error("Unauthorized", 401)
            if request.method != "GET" and int(user.get("permission_level", 0)) < int(PermissionLevel.ADMIN):
                return error("Admin permission required", 403)

        @self.blueprint.route("/records", methods=["GET"])
        def api_records():
            category = request.args.get("category") or None
            owner = request.args.get("owner") or None
            levels = [level for level in request.args.get("levels", "").split(",") if level]
            limit = int(request.args.get("limit", "500"))
            records = self.kernel.logs.query(category=category, owner=owner, levels=levels, limit=limit)
            return jsonify({"success": True, "data": {"records": records, "session": self.kernel.logs.session_id}})

        @self.blueprint.route("/files", methods=["GET"])
        def api_files():
            return jsonify({"success": True, "data": {"files": self.kernel.logs.list_files(), "session": self.kernel.logs.session_id}})

        @self.blueprint.route("/download", methods=["GET"])
        def api_download():
            category = request.args.get("category", "core")
            owner = request.args.get("owner", "core")
            content = self.kernel.logs.read_file(category, owner)
            return Response(
                content,
                mimetype="text/plain; charset=utf-8",
                headers={"Content-Disposition": f"attachment; filename={category}-{owner}-{self.kernel.logs.session_id}.log"},
            )

        @self.blueprint.route("/settings", methods=["GET", "POST"])
        def api_settings():
            config = self.load_config()
            if request.method == "POST":
                data = request.get_json(silent=True) or {}
                for key in ("level", "max_total_mb", "max_age_days"):
                    if key in data:
                        config[key] = data[key]
                try:
                    config["max_total_mb"] = max(1, int(config.get("max_total_mb", DEFAULT_CONFIG["max_total_mb"])))
                    config["max_age_days"] = max(0, int(config.get("max_age_days", DEFAULT_CONFIG["max_age_days"])))
                    self.apply_config(config)
                    self.save_config(config)
                except ValueError as e:
                    return jsonify({"success": False, "errorMessage": str(e)}), 400

            prune_result = self.apply_config(config)
            return jsonify({
                "success": True,
                "data": {
                    "level": self.kernel.logs.get_level_name(),
                    "max_total_mb": config["max_total_mb"],
                    "max_age_days": config["max_age_days"],
                    "session": self.kernel.logs.session_id,
                    "session_dir": self.kernel.logs.session_dir,
                    "prune": prune_result,
                },
            })

        @self.blueprint.route("/web", methods=["POST"])
        def api_web_log():
            data = request.get_json(silent=True) or {}
            level = str(data.get("level", "INFO")).lower()
            message = str(data.get("message", ""))
            logger = logging.getLogger("conductor.web.frontend")
            getattr(logger, level if level in {"debug", "info", "warning", "error", "critical"} else "info")(message)
            return jsonify({"success": True})

    def _register_commands(self) -> None:
        builder = SimpleCommandBuilder()
        builder.arg("level", Text)
        builder.arg("max_total_mb", Integer)
        builder.arg("max_age_days", Integer)
        builder.command("!!conductor logs status", self.cmd_log_status, PermissionLevel.ADMIN, "Show log session status", "core")
        builder.command("!!conductor logs level <level>", self.cmd_log_level, PermissionLevel.ADMIN, "Set root log level", "core")
        builder.command("!!conductor logs retention size <max_total_mb>", self.cmd_log_retention, PermissionLevel.ADMIN, "Set log storage max size in MB", "core")
        builder.command("!!conductor logs retention age <max_age_days>", self.cmd_log_retention, PermissionLevel.ADMIN, "Set log max age in days", "core")
        builder.command("!!conductor logs retention size <max_total_mb> age <max_age_days>", self.cmd_log_retention, PermissionLevel.ADMIN, "Set log retention policy", "core")
        builder.register(self.kernel)

    def cmd_log_level(self, source, ctx) -> None:
        level = ctx.get("level")
        try:
            config = self.load_config()
            config["level"] = level
            self.apply_config(config)
            self.save_config(config)
            source.reply(f"Log level set to {self.kernel.logs.get_level_name()}.")
        except ValueError as e:
            source.reply(str(e))

    def cmd_log_retention(self, source, ctx) -> None:
        config = self.load_config()
        max_total_mb = ctx.get("max_total_mb")
        max_age_days = ctx.get("max_age_days")
        if max_total_mb is not None:
            config["max_total_mb"] = max(1, int(max_total_mb))
        if max_age_days is not None:
            config["max_age_days"] = max(0, int(max_age_days))
        result = self.apply_config(config)
        self.save_config(config)
        source.reply(
            f"Log retention set: max_total_mb={config['max_total_mb']}, "
            f"max_age_days={config['max_age_days']}, pruned={len(result.get('removed', []))}"
        )

    def cmd_log_status(self, source, ctx) -> None:
        config = self.load_config()
        source.reply(
            "\n".join([
                "--- Log Manager ---",
                f"Session: {self.kernel.logs.session_id}",
                f"Level: {self.kernel.logs.get_level_name()}",
                f"Directory: {self.kernel.logs.session_dir}",
                f"Max total: {config.get('max_total_mb')} MB",
                f"Max age: {config.get('max_age_days')} days",
            ])
        )
