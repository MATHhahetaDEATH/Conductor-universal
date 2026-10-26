from __future__ import annotations

import logging
import os
import shutil
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, Iterable, Optional


LOG_FORMAT = "[%(asctime)s] [%(name)s/%(levelname)s]: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def infer_log_scope(record: logging.LogRecord) -> tuple[str, str]:
    plugin_id = getattr(record, "plugin_id", None)
    if plugin_id:
        return "plugin", str(plugin_id)
    if record.name.startswith("conductor.plugins."):
        parts = record.name.split(".")
        if len(parts) >= 3:
            return "plugin", parts[2]
    if record.name.startswith("conductor.web"):
        return "web", "frontend"
    return "core", "core"


class ConductorLogHandler(logging.Handler):
    """Dispatch every log record to the active Conductor logging session."""

    def __init__(self, manager: "ConductorLogManager") -> None:
        super().__init__()
        self.manager = manager
        self.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.manager.write_record(record, self.format(record))
        except Exception:
            self.handleError(record)


class ConductorLogManager:
    """Unified log interface for kernel, plugins, web APIs, files, and realtime views."""

    def __init__(self, logs_dir: str, level: int = logging.INFO, buffer_size: int = 2000) -> None:
        self.logs_dir = os.path.abspath(logs_dir)
        self.session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.session_dir = os.path.join(self.logs_dir, self.session_id)
        self.level = level
        self.buffer_size = buffer_size
        self._records: Deque[Dict[str, Any]] = deque(maxlen=buffer_size)
        self._handles: Dict[str, Any] = {}
        self._handler = ConductorLogHandler(self)
        os.makedirs(self.session_dir, exist_ok=True)

    def configure_root(self) -> None:
        root = logging.getLogger()
        root.setLevel(self.level)
        for handler in list(root.handlers):
            if isinstance(handler, ConductorLogHandler):
                root.removeHandler(handler)
        root.addHandler(self._handler)

    def set_level(self, level_name: str) -> None:
        level = getattr(logging, level_name.upper(), None)
        if not isinstance(level, int):
            raise ValueError(f"Unknown log level: {level_name}")
        self.level = level
        logging.getLogger().setLevel(level)
        self._handler.setLevel(level)

    def get_level_name(self) -> str:
        return logging.getLevelName(self.level)

    def write_record(self, record: logging.LogRecord, line: str) -> None:
        category, owner = infer_log_scope(record)
        rel_path = os.path.join(category, f"{owner}.log")
        abs_path = os.path.join(self.session_dir, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        handle = self._handles.get(rel_path)
        if handle is None:
            handle = open(abs_path, "a", encoding="utf-8")
            self._handles[rel_path] = handle

        handle.write(line + "\n")
        handle.flush()

        self._records.append({
            "timestamp": datetime.fromtimestamp(record.created).strftime(LOG_DATE_FORMAT),
            "logger": record.name,
            "level": record.levelname,
            "category": category,
            "owner": owner,
            "message": record.getMessage(),
            "line": line,
            "file": rel_path,
        })

    def query(
        self,
        category: Optional[str] = None,
        owner: Optional[str] = None,
        levels: Optional[Iterable[str]] = None,
        limit: int = 500,
    ) -> list[Dict[str, Any]]:
        level_set = {level.upper() for level in levels or [] if level}
        result = []
        for item in reversed(self._records):
            if category and item["category"] != category:
                continue
            if owner and item["owner"] != owner:
                continue
            if level_set and item["level"] not in level_set:
                continue
            result.append(item)
            if len(result) >= limit:
                break
        return list(reversed(result))

    def list_files(self) -> list[Dict[str, str]]:
        files = []
        for root, _, names in os.walk(self.session_dir):
            for name in names:
                if not name.endswith(".log"):
                    continue
                path = os.path.join(root, name)
                rel = os.path.relpath(path, self.session_dir)
                category = rel.split(os.sep, 1)[0]
                owner = os.path.splitext(os.path.basename(path))[0]
                files.append({"category": category, "owner": owner, "path": rel})
        return sorted(files, key=lambda item: item["path"])

    def read_file(self, category: str, owner: str) -> str:
        path = os.path.join(self.session_dir, category, f"{owner}.log")
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def prune_sessions(self, max_total_mb: int = 512, max_age_days: int = 14) -> dict:
        sessions = []
        now = datetime.now()
        for name in os.listdir(self.logs_dir):
            path = os.path.join(self.logs_dir, name)
            if not os.path.isdir(path) or name == self.session_id:
                continue
            try:
                created_at = datetime.strptime(name, "%Y%m%d-%H%M%S")
            except ValueError:
                continue
            size = self._dir_size(path)
            sessions.append({"name": name, "path": path, "created_at": created_at, "size": size})

        removed = []
        max_age = timedelta(days=max_age_days)
        for session in list(sessions):
            if max_age_days >= 0 and now - session["created_at"] > max_age:
                shutil.rmtree(session["path"], ignore_errors=True)
                removed.append(session["name"])
                sessions.remove(session)

        max_total_bytes = max_total_mb * 1024 * 1024
        total = sum(session["size"] for session in sessions) + self._dir_size(self.session_dir)
        for session in sorted(sessions, key=lambda item: item["created_at"]):
            if max_total_mb <= 0 or total <= max_total_bytes:
                break
            shutil.rmtree(session["path"], ignore_errors=True)
            removed.append(session["name"])
            total -= session["size"]

        return {"removed": removed, "total_bytes": total}

    def _dir_size(self, path: str) -> int:
        total = 0
        for root, _, names in os.walk(path):
            for name in names:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    continue
        return total

    def close(self) -> None:
        logging.getLogger().removeHandler(self._handler)
        for handle in self._handles.values():
            handle.close()
        self._handles.clear()
