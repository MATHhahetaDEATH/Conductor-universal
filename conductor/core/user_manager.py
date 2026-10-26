from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from typing import Any

from .permission import PermissionLevel


class UserManager:
    """Manage local users, password hashes, and API sessions."""

    def __init__(self, storage_dir: str) -> None:
        self.storage_dir = os.path.abspath(storage_dir)
        self.data_dir = os.path.join(self.storage_dir, "data", "core")
        self.users_file = os.path.join(self.data_dir, "users.json")
        self._lock = threading.RLock()
        self._sessions: dict[str, str] = {}
        os.makedirs(self.data_dir, exist_ok=True)
        self._ensure_owner()

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        """Return user data when username/password are valid."""
        user = self.get_user(username)
        if not user or user.get("disabled"):
            return None
        if not self._verify_password(password, user["password_hash"]):
            return None
        return user

    def create_session(self, username: str) -> str:
        """Create a bearer token for a user."""
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = username
        return token

    def revoke_session(self, token: str) -> None:
        """Remove a bearer token if it exists."""
        with self._lock:
            self._sessions.pop(token, None)

    def get_user_by_token(self, token: str | None) -> dict[str, Any] | None:
        """Return the user associated with a bearer token."""
        if not token:
            return None
        with self._lock:
            username = self._sessions.get(token)
        if not username:
            return None
        return self.get_user(username)

    def list_users(self) -> list[dict[str, Any]]:
        """Return public user records sorted by username."""
        with self._lock:
            users = self._load_users()
        return [
            self.public_user(user)
            for user in sorted(users.values(), key=lambda item: item["username"].lower())
        ]

    def get_user(self, username: str) -> dict[str, Any] | None:
        """Return a stored user record by username."""
        with self._lock:
            return self._load_users().get(username)

    def create_user(
        self,
        username: str,
        password: str,
        permission_level: int = PermissionLevel.USER,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a user and persist it."""
        username = self._normalize_username(username)
        if not password:
            raise ValueError("Password cannot be empty")
        permission_level = self._normalize_permission(permission_level)
        with self._lock:
            users = self._load_users()
            if username in users:
                raise ValueError("User already exists")
            users[username] = {
                "username": username,
                "display_name": display_name or username,
                "password_hash": self._hash_password(password),
                "permission_level": int(permission_level),
                "disabled": False,
                "created_at": self._now(),
            }
            self._save_users(users)
            return self.public_user(users[username])

    def update_user(self, username: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Update mutable user fields and persist them."""
        username = self._normalize_username(username)
        with self._lock:
            users = self._load_users()
            if username not in users:
                raise ValueError("User not found")
            user = users[username]

            if "display_name" in changes:
                user["display_name"] = str(changes.get("display_name") or username)
            if "permission_level" in changes:
                user["permission_level"] = int(
                    self._normalize_permission(changes["permission_level"])
                )
            if "disabled" in changes:
                if username == "root" and changes["disabled"]:
                    raise ValueError("Root owner account cannot be disabled")
                user["disabled"] = bool(changes["disabled"])
            if changes.get("password"):
                user["password_hash"] = self._hash_password(str(changes["password"]))

            users[username] = user
            self._save_users(users)
            return self.public_user(user)

    def delete_user(self, username: str) -> None:
        """Delete a user unless it is the built-in root account."""
        username = self._normalize_username(username)
        if username == "root":
            raise ValueError("Root owner account cannot be deleted")
        with self._lock:
            users = self._load_users()
            if username not in users:
                raise ValueError("User not found")
            users.pop(username)
            self._save_users(users)
            for token, token_user in list(self._sessions.items()):
                if token_user == username:
                    self._sessions.pop(token, None)

    def public_user(self, user: dict[str, Any]) -> dict[str, Any]:
        """Return a user record without secrets."""
        level = PermissionLevel(user.get("permission_level", PermissionLevel.USER))
        return {
            "username": user["username"],
            "name": user.get("display_name") or user["username"],
            "display_name": user.get("display_name") or user["username"],
            "permission_level": int(level),
            "permission_name": level.name,
            "disabled": bool(user.get("disabled", False)),
            "created_at": user.get("created_at"),
        }

    def _ensure_owner(self) -> None:
        with self._lock:
            users = self._load_users()
            root = users.get("root")
            if root:
                root["permission_level"] = int(PermissionLevel.OWNER)
                root.setdefault("display_name", "root")
                root.setdefault("disabled", False)
            else:
                users["root"] = {
                    "username": "root",
                    "display_name": "root",
                    "password_hash": self._hash_password("root"),
                    "permission_level": int(PermissionLevel.OWNER),
                    "disabled": False,
                    "created_at": self._now(),
                }
            self._save_users(users)

    def _load_users(self) -> dict[str, dict[str, Any]]:
        if not os.path.exists(self.users_file):
            return {}
        with open(self.users_file, "r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict) and "users" in data:
            return data["users"]
        return data if isinstance(data, dict) else {}

    def _save_users(self, users: dict[str, dict[str, Any]]) -> None:
        tmp_file = f"{self.users_file}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as file:
            json.dump({"users": users}, file, ensure_ascii=False, indent=2)
        os.replace(tmp_file, self.users_file)

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000
        ).hex()
        return f"pbkdf2_sha256$200000${salt}${digest}"

    def _verify_password(self, password: str, encoded: str) -> bool:
        try:
            algorithm, iterations, salt, expected = encoded.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            ).hex()
            return hmac.compare_digest(digest, expected)
        except ValueError:
            return False

    def _normalize_username(self, username: str) -> str:
        value = str(username or "").strip()
        if not value:
            raise ValueError("Username cannot be empty")
        return value

    def _normalize_permission(self, value: int) -> PermissionLevel:
        try:
            return PermissionLevel(int(value))
        except (TypeError, ValueError):
            raise ValueError("Invalid permission level") from None

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
