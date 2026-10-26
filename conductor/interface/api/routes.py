from functools import wraps
from typing import Callable

from flask import Flask, jsonify, request, send_from_directory
from pydantic import BaseModel, ValidationError
from conductor.core.permission import CommandSource, PermissionLevel
import os

class ContentData(BaseModel):
    id: str
    source: str
    payload: dict
    tags: list[str] = []

class CommandData(BaseModel):
    command: str

def register_routes(app: Flask, kernel) -> None:
    def _token_from_request() -> str | None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header.removeprefix("Bearer ").strip()
        return request.headers.get("X-Conductor-Token")

    def _current_user() -> dict | None:
        return kernel.users.get_user_by_token(_token_from_request())

    def _permission_payload(level: int) -> dict[str, list[str]]:
        permissions = {
            "permission.level": [PermissionLevel(level).name.lower()],
        }
        if level >= PermissionLevel.OWNER:
            permissions["*"] = ["*"]
            permissions["system.users"] = ["manage"]
        return permissions

    def _frontend_user(user: dict) -> dict:
        public = kernel.users.public_user(user)
        level = public["permission_level"]
        return {
            **public,
            "avatar": "https://lf1-xgcdn-tos.pstatp.com/obj/vcloud/vadmin/start.8e0e4855ee346a46ccff8ff3e24db27b.png",
            "email": "",
            "job": PermissionLevel(level).name.lower(),
            "jobName": PermissionLevel(level).name.title(),
            "organization": "Conductor",
            "organizationName": "Conductor",
            "location": "local",
            "locationName": "Local",
            "introduction": "Conductor local account",
            "personalWebsite": "",
            "verified": True,
            "phoneNumber": "",
            "accountId": public["username"],
            "registrationTime": public.get("created_at"),
            "permissions": _permission_payload(level),
        }

    def require_login(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = _current_user()
            if not user:
                return jsonify({"success": False, "errorMessage": "Unauthorized"}), 401
            return func(user, *args, **kwargs)

        return wrapper

    def require_owner(func: Callable):
        @require_login
        @wraps(func)
        def wrapper(user, *args, **kwargs):
            if int(user.get("permission_level", 0)) < PermissionLevel.OWNER:
                return jsonify({"success": False, "errorMessage": "Owner permission required"}), 403
            return func(user, *args, **kwargs)

        return wrapper

    @app.route("/api/user/login", methods=["POST"])
    def login():
        """Authenticate a user and return a session token."""
        data = request.get_json(silent=True) or {}
        username = data.get("userName") or data.get("username")
        password = data.get("password") or ""
        user = kernel.users.authenticate(username or "", password)
        if not user:
            return jsonify({"status": "error", "success": False, "msg": "账号或者密码错误"}), 401
        token = kernel.users.create_session(user["username"])
        return jsonify({
            "status": "ok",
            "success": True,
            "token": token,
            "user": _frontend_user(user),
        })

    @app.route("/api/user/logout", methods=["POST"])
    def logout():
        """Revoke the current session token."""
        token = _token_from_request()
        if token:
            kernel.users.revoke_session(token)
        return jsonify({"success": True})

    @app.route("/api/user/userInfo", methods=["GET"])
    @require_login
    def user_info(user):
        """Return the current logged-in user's frontend profile."""
        return jsonify(_frontend_user(user))

    @app.route("/api/users", methods=["GET"])
    @require_owner
    def list_users(_user):
        """Return all local users. OWNER only."""
        return jsonify({"success": True, "data": kernel.users.list_users()})

    @app.route("/api/users", methods=["POST"])
    @require_owner
    def create_user(_user):
        """Create a local user. OWNER only."""
        data = request.get_json(silent=True) or {}
        try:
            user = kernel.users.create_user(
                username=data.get("username") or data.get("userName") or "",
                password=data.get("password") or "",
                permission_level=data.get("permission_level", PermissionLevel.USER),
                display_name=data.get("display_name") or data.get("name"),
            )
            return jsonify({"success": True, "data": user}), 201
        except ValueError as exc:
            return jsonify({"success": False, "errorMessage": str(exc)}), 400

    @app.route("/api/users/<username>", methods=["PATCH"])
    @require_owner
    def update_user(_user, username):
        """Update a local user. OWNER only."""
        try:
            user = kernel.users.update_user(username, request.get_json(silent=True) or {})
            return jsonify({"success": True, "data": user})
        except ValueError as exc:
            return jsonify({"success": False, "errorMessage": str(exc)}), 400

    @app.route("/api/users/<username>", methods=["DELETE"])
    @require_owner
    def delete_user(_user, username):
        """Delete a local user. OWNER only."""
        try:
            kernel.users.delete_user(username)
            return jsonify({"success": True})
        except ValueError as exc:
            return jsonify({"success": False, "errorMessage": str(exc)}), 400

    @app.route("/api/static/plugins/<path:path>", methods=["GET"])
    def serve_plugin_static(path):
        """Serve static files for plugins (HTML/JS/CSS)."""
        plugin_id, _, asset_path = path.partition("/")
        if not plugin_id or not asset_path:
            return jsonify({"success": False, "errorMessage": "Invalid plugin asset path"}), 404

        plugin_path = kernel.plugins.plugin_file_map.get(plugin_id)
        if not plugin_path or not os.path.isdir(plugin_path):
            return jsonify({"success": False, "errorMessage": "Plugin asset source not found"}), 404

        web_dir = os.path.abspath(os.path.join(plugin_path, "web"))
        requested_path = os.path.abspath(os.path.join(web_dir, asset_path))
        if not requested_path.startswith(web_dir + os.sep):
            return jsonify({"success": False, "errorMessage": "Invalid plugin asset path"}), 403

        return send_from_directory(web_dir, asset_path)

    @app.route("/api/status", methods=["GET"])
    def status():
        """Returns the status of the Conductor kernel."""
        plugins = []
        for k, module in kernel.plugins.loaded_plugins.items():
            metadata = getattr(module, "PLUGIN_METADATA", {})
            plugins.append({
                "id": k, 
                "name": metadata.get("name", k),
                "version": metadata.get("version", "unknown"),
                "description": metadata.get("description", ""),
                "loaded": True
            })
        return jsonify({
            "success": True,
            "data": {
                "status": "running",
                "debug": getattr(kernel, "debug", False),
                "plugins": plugins
            }
        }), 200

    @app.route("/api/content", methods=["POST"])
    @require_login
    def receive_content(_user):
        """Endpoint to receive new content and trigger the kernel event."""
        try:
            data = ContentData(**request.json)
            # Dispatch event to the kernel
            kernel.dispatch_event("conductor.content_received", kernel, data)
            return jsonify({"success": True, "data": {"status": "received", "id": data.id}}), 202
        except ValidationError as e:
            return jsonify({"success": False, "errorCode": "VALIDATION_ERROR", "errorMessage": str(e.errors())}), 400
        except Exception as e:
            kernel.logger.error(f"Error processing content: {e}")
            return jsonify({"success": False, "errorCode": "INTERNAL_ERROR", "errorMessage": "Internal Server Error"}), 500

    @app.route("/api/command", methods=["POST"])
    @require_login
    def execute_command(user):
        """Endpoint to execute a registered command."""
        try:
            data = CommandData(**request.json)
            
            class ApiSource(CommandSource):
                def __init__(self):
                    super().__init__(
                        user["username"],
                        PermissionLevel(user.get("permission_level", PermissionLevel.USER)),
                    )
                    self.responses = []
                def reply(self, msg: str, plugin_id: str = "core"):
                    self.responses.append({"message": msg, "plugin_id": plugin_id})
            
            source = ApiSource()
            success = kernel.execute_command(source, data.command)
            
            if success:
                return jsonify({"success": True, "data": {"responses": source.responses}}), 200
            else:
                return jsonify({"success": False, "errorMessage": "Command execution failed", "data": {"responses": source.responses}}), 400
                
        except ValidationError as e:
            return jsonify({"success": False, "errorCode": "VALIDATION_ERROR", "errorMessage": str(e.errors())}), 400
