from __future__ import annotations

from copy import deepcopy

from flask import Blueprint, jsonify, request
from conductor.core.auth import current_user, error
from conductor.core.permission import PermissionLevel

from .registry import get_service

llm_bp = Blueprint("llm_provider", __name__)
_kernel_ref = None


@llm_bp.before_request
def require_llm_user():
    user = current_user(_kernel_ref) if _kernel_ref else None
    if not user:
        return error("Unauthorized", 401)
    if request.method in {"POST", "DELETE", "PUT", "PATCH"} and int(user.get("permission_level", 0)) < int(PermissionLevel.ADMIN):
        return error("Admin permission required", 403)


@llm_bp.route("/status", methods=["GET"])
def api_status():
    return jsonify({"success": True, "data": get_service().status()})


@llm_bp.route("/providers", methods=["GET"])
def api_providers():
    service = get_service()
    providers = deepcopy(service.config.get("providers", {}))
    return jsonify({"success": True, "data": service._mask_config({"providers": providers})["providers"]})


@llm_bp.route("/routing", methods=["GET", "POST"])
def api_routing():
    service = get_service()
    if request.method == "POST":
        try:
            data = service.update_routing(request.get_json(silent=True) or {})
            return jsonify({"success": True, "data": data})
        except Exception as exc:
            return jsonify({"success": False, "errorMessage": str(exc)}), 400
    return jsonify({"success": True, "data": deepcopy(service.config.get("routing", {}))})


@llm_bp.route("/providers/<provider_id>", methods=["POST", "DELETE"])
def api_provider_detail(provider_id: str):
    service = get_service()
    if request.method == "DELETE":
        try:
            service.delete_provider(provider_id)
            return jsonify({"success": True})
        except Exception as exc:
            return jsonify({"success": False, "errorMessage": str(exc)}), 400
    try:
        data = service.upsert_provider(provider_id, request.get_json(silent=True) or {})
        return jsonify({"success": True, "data": service._mask_config({"provider": data})["provider"]})
    except Exception as exc:
        return jsonify({"success": False, "errorMessage": str(exc)}), 400


@llm_bp.route("/models", methods=["GET"])
def api_models():
    return jsonify({"success": True, "data": get_service().list_local_models()})


@llm_bp.route("/complete", methods=["POST"])
def api_complete():
    data = request.get_json(silent=True) or {}
    try:
        result = get_service().complete(
            prompt=str(data.get("prompt", "")),
            plugin_id=str(data.get("plugin_id", "api")),
            system_prompt=data.get("system_prompt"),
            provider=data.get("provider"),
            tier=data.get("tier"),
            options=data.get("options") or {},
            timeout=float(data.get("timeout", 120)),
        )
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        return jsonify({"success": False, "errorMessage": str(exc)}), 400


@llm_bp.route("/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or {}
    try:
        result = get_service().chat(
            messages=data.get("messages") or [],
            plugin_id=str(data.get("plugin_id", "api")),
            provider=data.get("provider"),
            tier=data.get("tier"),
            options=data.get("options") or {},
            timeout=float(data.get("timeout", 120)),
        )
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        return jsonify({"success": False, "errorMessage": str(exc)}), 400


@llm_bp.route("/vision", methods=["POST"])
def api_vision():
    data = request.get_json(silent=True) or {}
    try:
        result = get_service().vision(
            prompt=str(data.get("prompt", "")),
            images=data.get("images") or data.get("image") or [],
            plugin_id=str(data.get("plugin_id", "api")),
            system_prompt=data.get("system_prompt"),
            provider=data.get("provider"),
            tier=data.get("tier") or "vl",
            options=data.get("options") or {},
            timeout=float(data.get("timeout", 120)),
        )
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        return jsonify({"success": False, "errorMessage": str(exc)}), 400


@llm_bp.route("/embed", methods=["POST"])
def api_embed():
    data = request.get_json(silent=True) or {}
    try:
        result = get_service().embed(
            inputs=data.get("inputs") or data.get("input") or [],
            plugin_id=str(data.get("plugin_id", "api")),
            provider=data.get("provider"),
            tier=data.get("tier") or "eb",
            options=data.get("options") or {},
            timeout=float(data.get("timeout", 120)),
        )
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        return jsonify({"success": False, "errorMessage": str(exc)}), 400


@llm_bp.route("/jobs", methods=["POST"])
def api_enqueue_job():
    data = request.get_json(silent=True) or {}
    try:
        raw_options = data.get("options") or {}
        options = raw_options if isinstance(raw_options, dict) else {}
        if "timeout" in data and "timeout" not in options:
            options = {**options, "timeout": float(data["timeout"])}
        job_id = get_service().enqueue(
            plugin_id=str(data.get("plugin_id", "api")),
            prompt=data.get("prompt"),
            messages=data.get("messages"),
            system_prompt=data.get("system_prompt"),
            provider=data.get("provider"),
            tier=data.get("tier"),
            options=options,
        )
        return jsonify({"success": True, "data": {"job_id": job_id}})
    except Exception as exc:
        return jsonify({"success": False, "errorMessage": str(exc)}), 400


@llm_bp.route("/jobs/<job_id>", methods=["GET"])
def api_get_job(job_id: str):
    job = get_service().get_job(job_id)
    if not job:
        return jsonify({"success": False, "errorMessage": "Job not found"}), 404
    return jsonify({"success": True, "data": job.to_dict(include_messages=True)})
