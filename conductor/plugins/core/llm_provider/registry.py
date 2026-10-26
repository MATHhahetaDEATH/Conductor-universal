from __future__ import annotations

from typing import Any

from .service import LLMProviderService

_service: LLMProviderService | None = None


def set_service(service: LLMProviderService | None) -> None:
    global _service
    _service = service


def get_service() -> LLMProviderService:
    if _service is None:
        raise RuntimeError("llm_provider is not loaded")
    return _service


def complete(prompt: str, **kwargs: Any) -> dict[str, Any]:
    return get_service().complete(prompt, **kwargs)


def chat(messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    return get_service().chat(messages, **kwargs)


def vision(prompt: str, images: list[str] | str, **kwargs: Any) -> dict[str, Any]:
    return get_service().vision(prompt, images, **kwargs)


def enqueue(**kwargs: Any) -> str:
    return get_service().enqueue(**kwargs)


def embed(inputs: list[str] | str, **kwargs: Any) -> dict[str, Any]:
    return get_service().embed(inputs, **kwargs)
