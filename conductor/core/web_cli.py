from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import BaseModel, ValidationError

from .auth import require_admin
from .permission import CommandSource, PermissionLevel


core_cli_bp = Blueprint("core_cli", __name__)


class SuggestRequest(BaseModel):
    input: str


class ExecuteRequest(BaseModel):
    input: str


def register_web_cli(kernel) -> None:
    @core_cli_bp.get("/info")
    @require_admin(kernel)
    def info(_user):
        plugin_id = request.args.get("plugin_id")
        commands = kernel.get_all_commands()
        if plugin_id:
            commands = [item for item in commands if item["plugin_id"] == plugin_id]
        return jsonify({"success": True, "data": {"commands": commands}})

    @core_cli_bp.post("/suggest")
    @require_admin(kernel)
    def suggest(_user):
        try:
            data = SuggestRequest.model_validate(request.get_json(silent=True) or {})
        except ValidationError as exc:
            return jsonify({"success": False, "errorCode": "VALIDATION_ERROR", "errorMessage": str(exc)}), 400
        return jsonify({"success": True, "data": {"suggestions": kernel.generate_suggestions(data.input)}})

    @core_cli_bp.post("/execute")
    @require_admin(kernel)
    def execute(user):
        try:
            data = ExecuteRequest.model_validate(request.get_json(silent=True) or {})
        except ValidationError as exc:
            return jsonify({"success": False, "errorCode": "VALIDATION_ERROR", "errorMessage": str(exc)}), 400

        class ApiSource(CommandSource):
            def __init__(self):
                super().__init__(user["username"], PermissionLevel(user.get("permission_level", PermissionLevel.USER)))
                self.responses = []

            def reply(self, message: str, plugin_id: str = "core") -> None:
                self.responses.append({"message": message, "plugin_id": plugin_id})

        source = ApiSource()
        success = kernel.execute_command(source, data.input)
        return jsonify({"success": success, "data": {"success": success, "responses": source.responses}}), 200 if success else 400
