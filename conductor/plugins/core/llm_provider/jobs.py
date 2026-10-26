from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMJob:
    job_id: str
    plugin_id: str
    provider: str
    messages: list[dict[str, Any]]
    options: dict[str, Any]
    inputs: list[str] = field(default_factory=list)
    requested_target: str | None = None
    tier: str | None = None
    selector: str | None = None
    model_name: str | None = None
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    traceback: str | None = None
    event: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self, include_messages: bool = False) -> dict[str, Any]:
        data = {
            "job_id": self.job_id,
            "plugin_id": self.plugin_id,
            "provider": self.provider,
            "requested_target": self.requested_target,
            "tier": self.tier,
            "selector": self.selector,
            "model_name": self.model_name,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
        }
        if include_messages:
            data["messages"] = self.messages
            data["inputs"] = self.inputs
        return data
