from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import jsonify, request

from .permission import PermissionLevel


def token_from_request() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header.removeprefix("Bearer ").strip() or None
    return request.headers.get("X-Conductor-Token") or None


def current_user(kernel) -> dict[str, Any] | None:
    return kernel.users.get_user_by_token(token_from_request())


def error(message: str, status: int):
    return jsonify({"success": False, "errorCode": "AUTH_ERROR", "errorMessage": message}), status


def require_login(kernel):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = current_user(kernel)
            if not user:
                return error("Unauthorized", 401)
            return func(user, *args, **kwargs)

        return wrapper

    return decorator


def require_permission(kernel, minimum: PermissionLevel):
    def decorator(func: Callable):
        @wraps(func)
        @require_login(kernel)
        def wrapper(user, *args, **kwargs):
            if int(user.get("permission_level", 0)) < int(minimum):
                return error(f"{minimum.name.title()} permission required", 403)
            return func(user, *args, **kwargs)

        return wrapper

    return decorator


def require_admin(kernel):
    return require_permission(kernel, PermissionLevel.ADMIN)


def require_owner(kernel):
    return require_permission(kernel, PermissionLevel.OWNER)
