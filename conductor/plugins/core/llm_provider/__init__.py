from __future__ import annotations

from typing import Any

from .api import llm_bp
from . import api as llm_api
from .commands import register_commands
from .constants import PLUGIN_ID
from .registry import chat, complete, embed, enqueue, get_service, set_service, vision
from .service import LLMProviderService

PLUGIN_METADATA = {
    "id": PLUGIN_ID,
    "version": "1.0.0",
    "name": "LLM Provider",
    "description": "Shared queued LLM gateway for local llama.cpp and online API providers.",
    "author": "kasumitang",
    "priority": 980,
    "web_name": "LLM Provider",
    "web_icon": "code",
    "web_hide_in_menu": False,
}

__all__ = [
    "LLMProviderService",
    "PLUGIN_METADATA",
    "chat",
    "complete",
    "embed",
    "enqueue",
    "get_service",
    "on_load",
    "on_unload",
    "vision",
]


def on_load(kernel, prev_module: Any) -> None:
    service = LLMProviderService(kernel)
    set_service(service)
    setattr(kernel, "llm_provider", service)
    llm_api._kernel_ref = kernel
    kernel.register_blueprint(llm_bp, url_prefix="/api/llm")
    register_commands(kernel)
    kernel.logger.info("LLM Provider plugin loaded.")


def on_unload(kernel) -> None:
    try:
        service = get_service()
    except RuntimeError:
        service = None
    if service is not None:
        service.stop()
    if getattr(kernel, "llm_provider", None) is service:
        delattr(kernel, "llm_provider")
    set_service(None)
    kernel.logger.info("LLM Provider plugin unloaded.")
