from __future__ import annotations

import multiprocessing
import os
import queue
import sys
import traceback
from copy import deepcopy
from logging import Logger
from typing import Any


def _ensure_plugin_package_importable() -> None:
    package_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if package_parent not in sys.path:
        sys.path.insert(0, package_parent)


def run_llama_cpp_subprocess(payload: dict[str, Any], result_queue: Any) -> None:
    try:
        from llama_cpp import Llama
        import llama_cpp.llama_chat_format as lcf

        provider_config = payload["provider_config"]
        mode = str(payload["mode"])
        model_path = str(payload["model_path"])
        embedding = mode == "embedding"

        chat_handler = None
        if mode == "vision":
            handler_name = str(payload.get("handler_name") or "").strip()
            handler_cls = getattr(lcf, handler_name, None)
            if handler_cls is None:
                raise RuntimeError(f"llama-cpp-python does not provide chat handler: {handler_name}")
            chat_handler = handler_cls(
                str(provider_config.get("mmproj_path") or "").strip(),
                verbose=bool(provider_config.get("verbose", False)),
            )

        llm = Llama(
            model_path=model_path,
            n_ctx=int(provider_config.get("n_ctx", 4096)),
            n_gpu_layers=int(provider_config.get("n_gpu_layers", 0)),
            embedding=embedding,
            chat_handler=chat_handler,
            verbose=bool(provider_config.get("verbose", False)),
        )

        if mode == "embedding":
            inputs = payload.get("inputs") or []
            raw = llm.create_embedding(inputs if len(inputs) > 1 else inputs[0])
            result_queue.put({"ok": True, "raw": raw})
            return

        raw = llm.create_chat_completion(**(payload.get("request_payload") or {}))
        result_queue.put({"ok": True, "raw": raw})
    except Exception as exc:
        result_queue.put({"ok": False, "error": str(exc), "traceback": traceback.format_exc()})


def run_llama_cpp_request(
    *,
    provider_config: dict[str, Any],
    model_path: str,
    mode: str,
    request_payload: dict[str, Any] | None = None,
    inputs: list[str] | None = None,
    handler_name: str = "",
    timeout_seconds: float = 120,
    logger: Logger | None = None,
) -> dict[str, Any]:
    _ensure_plugin_package_importable()
    timeout = max(1.0, float(timeout_seconds))
    ctx = multiprocessing.get_context("spawn")
    result_queue: Any = ctx.Queue()
    process = ctx.Process(
        target=run_llama_cpp_subprocess,
        args=(
            {
                "provider_config": deepcopy(provider_config),
                "model_path": model_path,
                "mode": mode,
                "request_payload": deepcopy(request_payload or {}),
                "inputs": deepcopy(inputs or []),
                "handler_name": handler_name,
            },
            result_queue,
        ),
        daemon=True,
    )
    process.start()
    process.join(timeout=timeout)

    if process.is_alive():
        if logger:
            logger.error(
                "Local llama.cpp subprocess timed out after %.1fs; terminating pid=%s model=%s mode=%s",
                timeout,
                process.pid,
                model_path,
                mode,
            )
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
        raise TimeoutError(f"Local llama.cpp subprocess timed out after {timeout:.1f}s")

    if process.exitcode and process.exitcode != 0:
        raise RuntimeError(f"Local llama.cpp subprocess crashed with exit code {process.exitcode}")

    try:
        result = result_queue.get_nowait()
    except queue.Empty as exc:
        raise RuntimeError("Local llama.cpp subprocess exited without returning a result") from exc

    if not result.get("ok"):
        error = str(result.get("error") or "Local llama.cpp subprocess failed")
        child_traceback = str(result.get("traceback") or "").strip()
        if child_traceback:
            error = f"{error}\n{child_traceback}"
        raise RuntimeError(error)
    return result.get("raw") or {}
