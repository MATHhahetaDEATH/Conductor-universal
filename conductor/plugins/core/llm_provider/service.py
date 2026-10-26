from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from copy import deepcopy
from typing import Any

from .constants import DEFAULT_CONFIG, PLUGIN_ID, TIER_ALIASES, TIER_VALUES
from .jobs import LLMJob
from .local_runtime import run_llama_cpp_request


class LLMProviderService:
    """Queued LLM gateway shared by plugins and REST callers."""

    def __init__(self, kernel: Any) -> None:
        self.kernel = kernel
        self.logger = kernel.get_logger(PLUGIN_ID)
        self.config_path = os.path.join(kernel.get_plugin_config_dir(PLUGIN_ID), "config.json")
        self.config = self._load_config()
        self.jobs: dict[str, LLMJob] = {}
        self.job_order: list[str] = []
        self.lock = threading.RLock()
        self.dispatch_condition = threading.Condition(self.lock)
        self._pending_jobs: list[LLMJob] = []
        self._running_jobs: dict[str, threading.Thread] = {}
        self._active_local_jobs = 0
        self._active_online_slots: dict[str, int] = {}
        self._tier_round_robin: dict[str, int] = {tier: 0 for tier in TIER_VALUES}
        self._last_llama_cpp_debug: dict[str, Any] | None = None
        self._stop_event = threading.Event()
        self._dispatcher = threading.Thread(target=self._dispatch_loop, name="llm-provider-dispatcher", daemon=True)
        self._dispatcher.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self.dispatch_condition:
            self.dispatch_condition.notify_all()
        self._dispatcher.join(timeout=2)
        for thread in list(self._running_jobs.values()):
            thread.join(timeout=2)

    def status(self) -> dict[str, Any]:
        with self.lock:
            catalog = self._build_model_catalog_locked()
            tier_summary = {}
            for tier in TIER_VALUES:
                tier_summary[tier] = {
                    "count": len([item for item in catalog if item.get("tier") == tier and item.get("enabled", True)]),
                }
            return {
                "queue_size": len(self._pending_jobs),
                "worker_alive": self._dispatcher.is_alive(),
                "selectable_models": catalog,
                "tiers": tier_summary,
                "routing": deepcopy(self.config.get("routing", {})),
                "capacity": {
                    "local_active": self._active_local_jobs,
                    "online_active": deepcopy(self._active_online_slots),
                },
                "runtime": {
                    "llama_cpp_available": importlib.util.find_spec("llama_cpp") is not None,
                    "llama_cpp_chat_handlers": self._list_llama_chat_handlers(),
                    "python_executable": sys.executable,
                },
                "last_llama_cpp_debug": deepcopy(self._last_llama_cpp_debug),
                "recent_jobs": [self.jobs[job_id].to_dict() for job_id in self.job_order[-20:]],
            }

    def upsert_provider(self, provider_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not provider_id.strip():
            raise ValueError("provider_id is required")
        with self.lock:
            merged = deepcopy(self.config)
            providers = merged.setdefault("providers", {})
            current = deepcopy(providers.get(provider_id, {}))
            self._preserve_masked_secrets(payload, current)
            self._deep_update(current, payload)
            providers[provider_id] = current
            self.config = self._normalize_config(merged)
            self._save_config()
            return deepcopy(self.config["providers"][provider_id])

    def delete_provider(self, provider_id: str) -> None:
        with self.lock:
            providers = self.config.get("providers", {})
            if provider_id not in providers:
                raise ValueError(f"Unknown LLM provider: {provider_id}")
            providers.pop(provider_id, None)
            for tier, routing in self.config.get("routing", {}).items():
                if str(routing.get("default_provider") or "") == provider_id:
                    self.config["routing"][tier]["default_provider"] = ""
            self._save_config()

    def update_routing(self, patch: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            merged = deepcopy(self.config)
            routing = merged.setdefault("routing", {})
            for tier, payload in patch.items():
                normalized_tier = self._normalize_tier(tier)
                if not normalized_tier:
                    raise ValueError(f"Unknown tier: {tier}")
                current = deepcopy(routing.get(normalized_tier, {}))
                if isinstance(payload, dict):
                    self._deep_update(current, payload)
                routing[normalized_tier] = current
            self.config = self._normalize_config(merged)
            self._save_config()
            return deepcopy(self.config.get("routing", {}))

    def list_local_models(self) -> dict[str, list[dict[str, Any]]]:
        models_dir = os.path.join(self.kernel.get_plugin_data_dir(PLUGIN_ID), "models")
        os.makedirs(models_dir, exist_ok=True)
        model_suffixes = {".gguf", ".bin"}
        mmproj_suffixes = {".gguf", ".bin", ".ggml", ".mmproj"}
        models = []
        mmprojs = []
        for root, _, names in os.walk(models_dir):
            for name in sorted(names):
                if name.startswith(".") or name.startswith("._"):
                    continue
                path = os.path.join(root, name)
                ext = os.path.splitext(name)[1].lower()
                if not os.path.isfile(path):
                    continue
                rel_path = os.path.relpath(path, models_dir)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    size = 0
                item = {
                    "id": rel_path,
                    "name": name,
                    "path": path,
                    "size": size,
                }
                lowered = name.lower()
                if ext in model_suffixes:
                    models.append(item)
                if "mmproj" in lowered or "projector" in lowered or (ext in mmproj_suffixes and "vision" in lowered):
                    mmprojs.append(item)
        return {
            "models": sorted(models, key=lambda item: item["id"]),
            "mmprojs": sorted(mmprojs, key=lambda item: item["id"]),
        }

    def complete(
        self,
        prompt: str,
        plugin_id: str = "core",
        system_prompt: str | None = None,
        provider: str | None = None,
        tier: str | None = None,
        options: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        job_id = self.enqueue(
            plugin_id=plugin_id,
            prompt=prompt,
            system_prompt=system_prompt,
            provider=provider,
            tier=tier,
            options=self._options_with_timeout(options, timeout),
        )
        return self.wait(job_id, timeout=timeout)

    def chat(
        self,
        messages: list[dict[str, Any]],
        plugin_id: str = "core",
        provider: str | None = None,
        tier: str | None = None,
        options: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        job_id = self.enqueue(
            plugin_id=plugin_id,
            messages=messages,
            provider=provider,
            tier=tier,
            options=self._options_with_timeout(options, timeout),
        )
        return self.wait(job_id, timeout=timeout)

    def vision(
        self,
        prompt: str,
        images: list[str] | str,
        plugin_id: str = "core",
        system_prompt: str | None = None,
        provider: str | None = None,
        tier: str | None = "vl",
        options: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        normalized_images = [images] if isinstance(images, str) else list(images)
        job_id = self.enqueue(
            plugin_id=plugin_id,
            prompt=prompt,
            images=normalized_images,
            system_prompt=system_prompt,
            provider=provider,
            tier=tier,
            options=self._options_with_timeout(options, timeout),
        )
        return self.wait(job_id, timeout=timeout)

    def embed(
        self,
        inputs: list[str] | str,
        plugin_id: str = "core",
        provider: str | None = None,
        tier: str | None = "eb",
        options: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        normalized_inputs = [inputs] if isinstance(inputs, str) else list(inputs)
        job_id = self.enqueue(
            plugin_id=plugin_id,
            provider=provider,
            tier=tier,
            inputs=normalized_inputs,
            options=self._options_with_timeout(options, timeout),
        )
        return self.wait(job_id, timeout=timeout)

    def enqueue(
        self,
        plugin_id: str,
        prompt: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        images: list[str] | None = None,
        inputs: list[str] | None = None,
        system_prompt: str | None = None,
        provider: str | None = None,
        tier: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        request_target, resolved_tier, merged_options, final_messages, final_inputs = self._prepare_request(
            plugin_id=plugin_id,
            prompt=prompt,
            messages=messages,
            images=images,
            inputs=inputs,
            system_prompt=system_prompt,
            provider=provider,
            tier=tier,
            options=options,
        )
        job = LLMJob(
            job_id=str(uuid.uuid4()),
            plugin_id=plugin_id,
            provider="",
            messages=final_messages,
            inputs=final_inputs,
            options=merged_options,
            requested_target=request_target,
            tier=resolved_tier,
        )
        with self.lock:
            self.jobs[job.job_id] = job
            self.job_order.append(job.job_id)
            self._prune_jobs_locked()
            self._pending_jobs.append(job)
            self.dispatch_condition.notify_all()
        self.kernel.dispatch_event("llm_provider.job_queued", job.to_dict(include_messages=True))
        return job.job_id

    def wait(self, job_id: str, timeout: float | None = None) -> dict[str, Any]:
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Unknown LLM job: {job_id}")
        if not job.event.wait(timeout=timeout):
            raise TimeoutError(f"LLM job timed out: {job_id}")
        if job.status == "failed":
            raise RuntimeError(job.error or "LLM job failed")
        return job.result or {}

    def get_job(self, job_id: str) -> LLMJob | None:
        with self.lock:
            return self.jobs.get(job_id)

    def _dispatch_loop(self) -> None:
        while not self._stop_event.is_set():
            with self.dispatch_condition:
                dispatched = False
                while not self._stop_event.is_set():
                    scheduled = self._reserve_next_job_locked()
                    if scheduled:
                        job, candidate, provider_name, injected_options = scheduled
                        job.provider = provider_name
                        job.selector = str(candidate.get("selector") or provider_name)
                        job.model_name = str(candidate.get("name") or candidate.get("model") or provider_name)
                        job.options.update(injected_options)
                        thread = threading.Thread(
                            target=self._run_job,
                            args=(job,),
                            name=f"llm-provider-job-{job.job_id[:8]}",
                            daemon=True,
                        )
                        self._running_jobs[job.job_id] = thread
                        thread.start()
                        dispatched = True
                        break
                    if self._pending_jobs:
                        self.dispatch_condition.wait(timeout=0.5)
                    else:
                        self.dispatch_condition.wait()
                if not dispatched and self._stop_event.is_set():
                    return

    def _reserve_next_job_locked(self) -> tuple[LLMJob, dict[str, Any], str, dict[str, Any]] | None:
        for index, job in enumerate(self._pending_jobs):
            selection = self._select_candidate_for_job_locked(job)
            if selection is None:
                continue
            candidate, provider_name, injected_options = selection
            self._reserve_candidate_locked(candidate)
            self._pending_jobs.pop(index)
            return job, candidate, provider_name, injected_options
        return None

    def _select_candidate_for_job_locked(self, job: LLMJob) -> tuple[dict[str, Any], str, dict[str, Any]] | None:
        if job.requested_target:
            return self._select_concrete_candidate_locked(job.requested_target)
        if job.tier:
            return self._select_tier_candidate_locked(job.tier)
        raise ValueError("LLM job is missing selector or tier")

    def _select_concrete_candidate_locked(self, target: str) -> tuple[dict[str, Any], str, dict[str, Any]] | None:
        candidate = self._resolve_target_locked(target)
        if candidate is None or not candidate.get("enabled", True):
            raise ValueError(f"Unknown or disabled LLM target: {target}")
        if not self._candidate_has_capacity_locked(candidate):
            return None
        return candidate, str(candidate["provider"]), self._injected_options_for_candidate(candidate)

    def _select_tier_candidate_locked(self, tier: str) -> tuple[dict[str, Any], str, dict[str, Any]] | None:
        normalized_tier = self._normalize_tier(tier)
        if not normalized_tier:
            raise ValueError(f"Unknown LLM tier: {tier}")
        catalog = [
            item for item in self._build_model_catalog_locked()
            if item.get("enabled", True) and item.get("tier") == normalized_tier
        ]
        if not catalog:
            raise ValueError(f"No enabled LLM targets configured for tier: {normalized_tier}")

        routing = self.config.get("routing", {}).get(normalized_tier, {})
        default_provider = str(routing.get("default_provider") or "").strip()
        strategy = str(routing.get("strategy") or "balanced").strip().lower()

        if default_provider:
            default_candidate = next((item for item in catalog if item.get("selector") == default_provider), None)
            if default_candidate and self._candidate_has_capacity_locked(default_candidate):
                return default_candidate, str(default_candidate["provider"]), self._injected_options_for_candidate(default_candidate)

        online_available = [item for item in catalog if item.get("transport") != "local" and self._candidate_has_capacity_locked(item)]
        if online_available:
            candidate = self._choose_tier_candidate_locked(normalized_tier, online_available, strategy)
            return candidate, str(candidate["provider"]), self._injected_options_for_candidate(candidate)

        local_available = [item for item in catalog if item.get("transport") == "local" and self._candidate_has_capacity_locked(item)]
        if local_available:
            candidate = self._choose_tier_candidate_locked(normalized_tier, local_available, strategy)
            return candidate, str(candidate["provider"]), self._injected_options_for_candidate(candidate)
        return None

    def _choose_tier_candidate_locked(self, tier: str, candidates: list[dict[str, Any]], strategy: str) -> dict[str, Any]:
        if strategy == "priority":
            return sorted(candidates, key=lambda item: (self._candidate_load_locked(item), str(item.get("selector"))))[0]
        return self._choose_round_robin_candidate_locked(tier, candidates)

    def _choose_round_robin_candidate_locked(self, tier: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        ordered = sorted(candidates, key=lambda item: (self._candidate_load_locked(item), str(item.get("selector"))))
        start = self._tier_round_robin.get(tier, 0)
        candidate = ordered[start % len(ordered)]
        self._tier_round_robin[tier] = (start + 1) % max(1, len(ordered))
        return candidate

    def _candidate_load_locked(self, candidate: dict[str, Any]) -> int:
        if candidate.get("transport") == "local":
            return self._active_local_jobs
        return self._active_online_slots.get(str(candidate.get("selector")), 0)

    def _candidate_has_capacity_locked(self, candidate: dict[str, Any]) -> bool:
        if candidate.get("transport") == "local":
            return self._active_local_jobs < 1
        limit = max(1, int(candidate.get("max_concurrency", 1)))
        return self._active_online_slots.get(str(candidate.get("selector")), 0) < limit

    def _reserve_candidate_locked(self, candidate: dict[str, Any]) -> None:
        if candidate.get("transport") == "local":
            self._active_local_jobs += 1
            return
        selector = str(candidate.get("selector"))
        self._active_online_slots[selector] = self._active_online_slots.get(selector, 0) + 1

    def _release_candidate(self, job: LLMJob) -> None:
        with self.dispatch_condition:
            selector = str(job.selector or "")
            provider_type = self.config.get("providers", {}).get(job.provider, {}).get("type")
            if provider_type == "llama_cpp":
                self._active_local_jobs = max(0, self._active_local_jobs - 1)
            elif selector:
                current = self._active_online_slots.get(selector, 0)
                if current <= 1:
                    self._active_online_slots.pop(selector, None)
                else:
                    self._active_online_slots[selector] = current - 1
            self._running_jobs.pop(job.job_id, None)
            self.dispatch_condition.notify_all()

    def _run_job(self, job: LLMJob) -> None:
        job.status = "running"
        job.started_at = time.time()
        self.kernel.dispatch_event("llm_provider.job_started", job.to_dict(include_messages=True))
        try:
            result = self._generate(job)
            job.result = result
            job.status = "succeeded"
            self.kernel.dispatch_event("llm_provider.job_completed", job.to_dict())
        except Exception as exc:
            job.error = str(exc)
            job.traceback = traceback.format_exc()
            job.status = "failed"
            provider_type = self.config.get("providers", {}).get(job.provider, {}).get("type")
            if provider_type == "llama_cpp":
                self._set_last_llama_cpp_debug({
                    **deepcopy(self._last_llama_cpp_debug or {}),
                    "job_id": job.job_id,
                    "provider": job.provider,
                    "selector": job.selector,
                    "tier": job.tier,
                    "finished_at": time.time(),
                    "status": "failed",
                    "error": job.error,
                    "traceback": job.traceback,
                })
            self.logger.error(f"LLM job failed: {exc}", exc_info=True)
            self.kernel.dispatch_event("llm_provider.job_failed", job.to_dict())
        finally:
            job.finished_at = time.time()
            job.event.set()
            self._release_candidate(job)

    def _generate(self, job: LLMJob) -> dict[str, Any]:
        provider_config = self._get_provider(job.provider)
        provider_type = provider_config.get("type", "")
        if not provider_config.get("enabled", True):
            raise ValueError(f"Provider is disabled: {job.provider}")
        if job.tier == "eb":
            if provider_type == "openai_compatible":
                return self._embed_openai_compatible(job, provider_config)
            if provider_type == "llama_cpp":
                return self._embed_llama_cpp(job, provider_config)
            raise ValueError(f"Embedding is not supported by provider type: {provider_type}")
        if provider_type == "openai_compatible":
            return self._generate_openai_compatible(job, provider_config)
        if provider_type == "llama_cpp":
            return self._generate_llama_cpp(job, provider_config)
        raise ValueError(f"Unsupported provider type: {provider_type}")

    def _generate_openai_compatible(self, job: LLMJob, provider_config: dict[str, Any]) -> dict[str, Any]:
        base_url = str(provider_config.get("base_url") or "").rstrip("/")
        model = job.options.get("model") or provider_config.get("model")
        if not base_url:
            raise ValueError(f"Provider {job.provider} is missing base_url")
        if not model:
            raise ValueError(f"Provider {job.provider} is missing model")

        api_key = provider_config.get("api_key") or os.environ.get(str(provider_config.get("api_key_env") or ""))
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        headers.update(provider_config.get("headers") or {})

        payload = {
            "model": model,
            "messages": job.messages,
            "temperature": job.options.get("temperature", provider_config.get("temperature", 0.7)),
            "max_tokens": job.options.get("max_tokens", provider_config.get("max_tokens", 512)),
        }
        for key in ("top_p", "presence_penalty", "frequency_penalty", "stop"):
            if key in job.options:
                payload[key] = job.options[key]

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/chat/completions", data=data, headers=headers, method="POST")
        timeout = self._provider_timeout(job, provider_config, 60)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Online provider returned HTTP {exc.code}: {body}") from exc

        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return {
            "text": message.get("content", ""),
            "provider": job.provider,
            "selector": job.selector,
            "tier": job.tier,
            "model": raw.get("model", model),
            "usage": raw.get("usage", {}),
            "raw": raw,
        }

    def _embed_openai_compatible(self, job: LLMJob, provider_config: dict[str, Any]) -> dict[str, Any]:
        base_url = str(provider_config.get("base_url") or "").rstrip("/")
        model = job.options.get("model") or provider_config.get("model")
        if not base_url:
            raise ValueError(f"Provider {job.provider} is missing base_url")
        if not model:
            raise ValueError(f"Provider {job.provider} is missing model")
        if not job.inputs:
            raise ValueError("Embedding request requires one or more input texts")

        api_key = provider_config.get("api_key") or os.environ.get(str(provider_config.get("api_key_env") or ""))
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        headers.update(provider_config.get("headers") or {})

        payload = {
            "model": model,
            "input": job.inputs if len(job.inputs) > 1 else job.inputs[0],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/embeddings", data=data, headers=headers, method="POST")
        timeout = self._provider_timeout(job, provider_config, 60)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Embedding provider returned HTTP {exc.code}: {body}") from exc

        vectors = [item.get("embedding", []) for item in raw.get("data", [])]
        return {
            "embeddings": vectors,
            "provider": job.provider,
            "selector": job.selector,
            "tier": job.tier,
            "model": raw.get("model", model),
            "usage": raw.get("usage", {}),
            "raw": raw,
        }

    def _generate_llama_cpp(self, job: LLMJob, provider_config: dict[str, Any]) -> dict[str, Any]:
        model_path = job.options.get("model_path") or provider_config.get("model_path")
        if not model_path:
            raise ValueError(f"Provider {job.provider} is missing model_path")
        messages = deepcopy(job.messages)
        is_vl_request = self._is_vl_provider(provider_config)
        if is_vl_request:
            messages = self._normalize_llama_vl_messages(messages, provider_config)
        payload = {
            "messages": messages,
            "temperature": job.options.get("temperature", provider_config.get("temperature", 0.7)),
            "max_tokens": job.options.get("max_tokens", provider_config.get("max_tokens", 512)),
        }
        debug_snapshot = {
            "job_id": job.job_id,
            "provider": job.provider,
            "selector": job.selector,
            "tier": job.tier,
            "model_path": model_path,
            "n_ctx": int(provider_config.get("n_ctx", 4096)),
            "n_gpu_layers": int(provider_config.get("n_gpu_layers", 0)),
            "verbose": bool(provider_config.get("verbose", False)),
            "chat_handler": None,
            "mmproj_path": str(provider_config.get("mmproj_path") or ""),
            "payload": deepcopy(payload),
            "normalized_messages": deepcopy(messages),
            "started_at": time.time(),
            "status": "running",
        }
        if is_vl_request:
            debug_snapshot["chat_handler"] = self._resolve_vl_handler_name(provider_config)
        self._set_last_llama_cpp_debug(debug_snapshot)
        self.logger.info(
            "Starting llama.cpp subprocess job %s provider=%s tier=%s model=%s mmproj=%s handler=%s",
            job.job_id,
            job.provider,
            job.tier or "-",
            model_path,
            debug_snapshot["mmproj_path"] or "-",
            debug_snapshot["chat_handler"] or "-",
        )
        raw = run_llama_cpp_request(
            provider_config=provider_config,
            model_path=str(model_path),
            mode="vision" if is_vl_request else "chat",
            request_payload=payload,
            handler_name=debug_snapshot["chat_handler"] or "",
            timeout_seconds=self._provider_timeout(job, provider_config, 120),
            logger=self.logger,
        )
        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        self._set_last_llama_cpp_debug({
            **debug_snapshot,
            "finished_at": time.time(),
            "status": "succeeded",
            "response_preview": str(message.get("content", ""))[:1000],
            "usage": raw.get("usage", {}),
        })
        return {
            "text": message.get("content", ""),
            "provider": job.provider,
            "selector": job.selector,
            "tier": job.tier,
            "model": model_path,
            "usage": raw.get("usage", {}),
            "raw": raw,
        }

    def _embed_llama_cpp(self, job: LLMJob, provider_config: dict[str, Any]) -> dict[str, Any]:
        if not job.inputs:
            raise ValueError("Embedding request requires one or more input texts")
        model_path = job.options.get("model_path") or provider_config.get("model_path")
        if not model_path:
            raise ValueError(f"Provider {job.provider} is missing model_path")
        debug_snapshot = {
            "job_id": job.job_id,
            "provider": job.provider,
            "selector": job.selector,
            "tier": job.tier,
            "model_path": model_path,
            "n_ctx": int(provider_config.get("n_ctx", 4096)),
            "n_gpu_layers": int(provider_config.get("n_gpu_layers", 0)),
            "verbose": bool(provider_config.get("verbose", False)),
            "embedding": True,
            "inputs": deepcopy(job.inputs),
            "started_at": time.time(),
            "status": "running",
        }
        self._set_last_llama_cpp_debug(debug_snapshot)
        self.logger.info(
            "Starting llama.cpp embedding subprocess job %s provider=%s inputs=%s model=%s",
            job.job_id,
            job.provider,
            len(job.inputs),
            model_path,
        )
        raw = run_llama_cpp_request(
            provider_config=provider_config,
            model_path=str(model_path),
            mode="embedding",
            inputs=deepcopy(job.inputs),
            timeout_seconds=self._provider_timeout(job, provider_config, 120),
            logger=self.logger,
        )
        vectors = [item.get("embedding", []) for item in raw.get("data", [])]
        self._set_last_llama_cpp_debug({
            **debug_snapshot,
            "finished_at": time.time(),
            "status": "succeeded",
            "embedding_count": len(vectors),
            "usage": raw.get("usage", {}),
        })
        return {
            "embeddings": vectors,
            "provider": job.provider,
            "selector": job.selector,
            "tier": job.tier,
            "model": model_path,
            "usage": raw.get("usage", {}),
            "raw": raw,
        }

    def _set_last_llama_cpp_debug(self, snapshot: dict[str, Any]) -> None:
        with self.lock:
            self._last_llama_cpp_debug = self._sanitize_debug_value(snapshot)

    def _normalize_llama_vl_messages(self, messages: list[dict[str, Any]], provider_config: dict[str, Any]) -> list[dict[str, Any]]:
        handler_name = self._resolve_vl_handler_name(provider_config)
        system_parts: list[str] = []
        normalized: list[dict[str, Any]] = []

        for message in messages:
            role = str(message.get("role") or "").strip().lower()
            content = message.get("content")
            if role == "system":
                system_text = self._extract_text_from_message_content(content)
                if system_text:
                    system_parts.append(system_text)
                continue

            if role != "user":
                normalized.append(deepcopy(message))
                continue

            image_parts, text_parts, other_parts = self._split_multimodal_user_content(content)
            combined_text_parts = [part for part in [*system_parts, *text_parts] if part]
            system_parts = []

            if image_parts:
                rebuilt_content: list[dict[str, Any]] = []
                if self._prefers_image_first(handler_name):
                    rebuilt_content.extend(image_parts)
                if combined_text_parts:
                    rebuilt_content.append({"type": "text", "text": "\n\n".join(combined_text_parts)})
                rebuilt_content.extend(other_parts)
                if not self._prefers_image_first(handler_name):
                    rebuilt_content.extend(image_parts)
                normalized.append({"role": "user", "content": rebuilt_content})
                continue

            if combined_text_parts:
                normalized.append({"role": "user", "content": "\n\n".join(combined_text_parts)})
            elif other_parts:
                normalized.append({"role": "user", "content": other_parts})

        if system_parts:
            fallback_text = "\n\n".join(system_parts)
            if normalized and str(normalized[-1].get("role") or "").strip().lower() == "user":
                trailing_content = normalized[-1].get("content")
                if isinstance(trailing_content, str):
                    normalized[-1]["content"] = f"{fallback_text}\n\n{trailing_content}".strip()
                elif isinstance(trailing_content, list):
                    trailing_content.insert(0, {"type": "text", "text": fallback_text})
                else:
                    normalized.append({"role": "user", "content": fallback_text})
            else:
                normalized.append({"role": "user", "content": fallback_text})

        return normalized

    def _extract_text_from_message_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "").strip().lower() == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
        return "\n\n".join(parts)

    def _split_multimodal_user_content(self, content: Any) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
        if isinstance(content, str):
            text = content.strip()
            return [], ([text] if text else []), []
        if not isinstance(content, list):
            return [], [], []

        image_parts: list[dict[str, Any]] = []
        text_parts: list[str] = []
        other_parts: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").strip().lower()
            if item_type == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    text_parts.append(text)
                continue
            if item_type == "image_url":
                image_url = item.get("image_url")
                if isinstance(image_url, dict) and str(image_url.get("url") or "").strip():
                    image_parts.append(deepcopy(item))
                continue
            other_parts.append(deepcopy(item))
        return image_parts, text_parts, other_parts

    def _is_vl_provider(self, provider_config: dict[str, Any]) -> bool:
        return self._normalize_tier(provider_config.get("tier")) == "vl"

    def _resolve_vl_handler_name(self, provider_config: dict[str, Any]) -> str:
        return str(provider_config.get("vl_handler") or "").strip()

    def _prefers_image_first(self, handler_name: str) -> bool:
        return handler_name == "Qwen25VLChatHandler"

    def _list_llama_chat_handlers(self) -> list[str]:
        try:
            import llama_cpp.llama_chat_format as lcf
        except ImportError:
            return []
        handlers = []
        for name in dir(lcf):
            value = getattr(lcf, name, None)
            if isinstance(value, type) and name.endswith("ChatHandler"):
                handlers.append(name)
        return sorted(handlers)

    def _sanitize_debug_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._sanitize_debug_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize_debug_value(item) for item in value]
        if isinstance(value, str):
            if value.startswith("data:image/") and ";base64," in value:
                prefix, encoded = value.split(",", 1)
                return f"{prefix},<base64:{len(encoded)} chars omitted>"
            if len(value) > 4000:
                return f"{value[:4000]}...<truncated {len(value) - 4000} chars>"
        return value

    def _prepare_request(
        self,
        plugin_id: str,
        prompt: str | None,
        messages: list[dict[str, Any]] | None,
        images: list[str] | None,
        inputs: list[str] | None,
        system_prompt: str | None,
        provider: str | None,
        tier: str | None,
        options: dict[str, Any] | None,
    ) -> tuple[str | None, str | None, dict[str, Any], list[dict[str, Any]], list[str]]:
        with self.lock:
            config = deepcopy(self.config)
        requested_target = provider
        requested_tier = tier
        if requested_target and self._normalize_tier(str(requested_target)):
            requested_tier = str(requested_target)
            requested_target = None
        if requested_target and str(requested_target).startswith("tier:"):
            requested_tier = str(requested_target).split(":", 1)[1]
            requested_target = None
        if not requested_target and not requested_tier:
            raise ValueError("No LLM provider selected")

        merged_options = deepcopy(options or {})
        normalized_tier = self._normalize_tier(requested_tier)
        if normalized_tier:
            requested_tier = normalized_tier
            requested_target = None
        elif requested_target:
            self._validate_requested_target(config, str(requested_target))

        final_messages = deepcopy(messages or [])
        final_inputs = [str(item) for item in (inputs or []) if str(item).strip()]
        final_images = [str(item).strip() for item in (images or []) if str(item).strip()]
        if prompt is not None:
            if requested_tier == "vl" and final_images:
                final_messages.append(self._build_vl_user_message(prompt, final_images))
            else:
                final_messages.append({"role": "user", "content": prompt})
        elif final_images:
            if requested_tier != "vl":
                raise ValueError("Image inputs require tier='vl' or a vision-language provider")
            final_messages.append(self._build_vl_user_message("", final_images))
        if requested_tier == "eb":
            if not final_inputs:
                raise ValueError("Embedding request requires input texts")
            return (str(requested_target) if requested_target else None), (str(requested_tier) if requested_tier else None), merged_options, [], final_inputs
        if final_images and requested_tier != "vl":
            raise ValueError("Image inputs require tier='vl'")
        if not final_messages:
            raise ValueError("LLM request requires prompt or messages")

        system_text = (system_prompt or "").strip()
        if system_text:
            final_messages = [{"role": "system", "content": system_text}] + final_messages
        return (str(requested_target) if requested_target else None), (str(requested_tier) if requested_tier else None), merged_options, final_messages, []

    def _build_vl_user_message(self, prompt: str, images: list[str]) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        prompt_text = str(prompt).strip()
        if prompt_text:
            content.append({"type": "text", "text": prompt_text})
        for image in images:
            content.append({"type": "image_url", "image_url": {"url": image}})
        if not content:
            raise ValueError("Vision request requires a prompt or at least one image")
        return {"role": "user", "content": content}

    def _get_provider(self, provider: str) -> dict[str, Any]:
        with self.lock:
            provider_config = deepcopy(self.config.get("providers", {}).get(provider))
        if not provider_config:
            raise ValueError(f"Unknown LLM provider: {provider}")
        return provider_config

    def _validate_requested_target(self, config: dict[str, Any], target: str) -> None:
        if target in config.get("providers", {}):
            return
        raise ValueError(f"Unknown LLM provider: {target}")

    def _load_config(self) -> dict[str, Any]:
        config = deepcopy(DEFAULT_CONFIG)
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._deep_update(config, json.load(f))
            except Exception as exc:
                self.logger.error(f"Failed to load LLM provider config: {exc}", exc_info=True)
        config = self._normalize_config(config)
        self.config = config
        self._save_config()
        return config

    def _save_config(self) -> None:
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def _normalize_config(self, config: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(DEFAULT_CONFIG)
        self._deep_update(merged, config)
        for stale_key in ("default_provider", "default_system_prompt", "plugin_defaults"):
            merged.pop(stale_key, None)
        merged.setdefault("routing", {})
        merged.setdefault("providers", {})
        for tier in TIER_VALUES:
            tier_routing = merged["routing"].setdefault(tier, {})
            tier_routing["default_provider"] = str(tier_routing.get("default_provider") or "")
            strategy = str(tier_routing.get("strategy") or "balanced").strip().lower()
            tier_routing["strategy"] = strategy if strategy in {"balanced", "priority"} else "balanced"
        for provider_name, provider in merged.get("providers", {}).items():
            provider.setdefault("display_name", provider_name)
            provider.setdefault("tags", [])
            provider["tags"] = [str(tag).strip() for tag in provider.get("tags", []) if str(tag).strip()]
            provider["tier"] = self._normalize_tier(provider.get("tier"))
            provider_type = provider.get("type")
            if provider_type == "llama_cpp":
                provider["max_concurrency"] = 1
                provider.setdefault("model_path", "")
                provider.setdefault("n_ctx", 4096)
                provider.setdefault("n_gpu_layers", 0)
                provider.setdefault("mmproj_path", "")
                provider.setdefault("vl_handler", "")
                provider.setdefault("timeout", 120)
                if provider.get("vl_handler") == "qwen3_vl":
                    provider["vl_handler"] = "Qwen25VLChatHandler"
                elif provider.get("vl_handler") == "internvl3":
                    provider["vl_handler"] = "MiniCPMv26ChatHandler"
            elif provider_type == "openai_compatible":
                provider["max_concurrency"] = max(1, int(provider.get("max_concurrency", 4)))
                provider.setdefault("base_url", "https://api.openai.com/v1")
                provider.setdefault("model", "")
                provider.setdefault("timeout", 60)
                provider.setdefault("capabilities", ["chat"])
                provider["capabilities"] = [str(item).strip() for item in provider.get("capabilities", []) if str(item).strip()]
        return merged

    def _mask_config(self, config: dict[str, Any]) -> dict[str, Any]:
        for provider in config.get("providers", {}).values():
            if provider.get("api_key"):
                provider["api_key"] = "***"
            for header_key in list((provider.get("headers") or {}).keys()):
                if "key" in header_key.lower() or "authorization" in header_key.lower():
                    provider["headers"][header_key] = "***"
        return config

    def _normalize_tier(self, value: Any) -> str:
        if value is None:
            return ""
        key = str(value).strip().lower()
        return TIER_ALIASES.get(key, "")

    def _resolve_target_locked(self, target: str) -> dict[str, Any] | None:
        for item in self._build_model_catalog_locked():
            if item.get("selector") == target:
                return item
        provider = self.config.get("providers", {}).get(target)
        if provider:
            return {
                "selector": target,
                "provider": target,
                "name": provider.get("display_name") or target,
                "model": provider.get("model") or provider.get("model_path") or target,
                "transport": "local" if provider.get("type") == "llama_cpp" else "online",
                "tier": provider.get("tier") or "",
                "enabled": provider.get("enabled", True),
                "max_concurrency": provider.get("max_concurrency", 1),
                "model_path": provider.get("model_path") or "",
                "base_url": provider.get("base_url") or "",
                "tags": provider.get("tags") or [],
                "capabilities": provider.get("capabilities") or [],
            }
        return None

    def _injected_options_for_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        if candidate.get("transport") == "local":
            return {"model_path": candidate.get("model_path")}
        return {}

    def _build_model_catalog_locked(self) -> list[dict[str, Any]]:
        config = deepcopy(self.config)
        catalog: list[dict[str, Any]] = []
        for provider_name, provider in config.get("providers", {}).items():
            provider_type = provider.get("type", "")
            catalog.append({
                "selector": provider_name,
                "provider": provider_name,
                "display_name": provider.get("display_name") or provider_name,
                "name": provider.get("display_name") or provider_name,
                "model": provider.get("model") or provider.get("model_path") or provider_name,
                "transport": "local" if provider_type == "llama_cpp" else "online",
                "tier": self._normalize_tier(provider.get("tier")),
                "enabled": bool(provider.get("enabled", True)),
                "max_concurrency": 1 if provider_type == "llama_cpp" else max(1, int(provider.get("max_concurrency", 4))),
                "base_url": provider.get("base_url") or "",
                "type": provider_type,
                "provider_id": provider_name,
                "provider_type": provider_type,
                "model_path": provider.get("model_path") or "",
                "mmproj_path": provider.get("mmproj_path") or "",
                "vl_handler": provider.get("vl_handler") or "",
                "n_ctx": provider.get("n_ctx", 4096),
                "n_gpu_layers": provider.get("n_gpu_layers", 0),
                "temperature": provider.get("temperature", 0.7),
                "max_tokens": provider.get("max_tokens", 512),
                "timeout": provider.get("timeout", 60),
                "tags": provider.get("tags") or [],
                "capabilities": provider.get("capabilities") or [],
            })
        return sorted(catalog, key=lambda item: (item.get("transport") != "online", str(item.get("name"))))

    def _prune_jobs_locked(self) -> None:
        max_recent = int(self.config.get("queue", {}).get("max_recent_jobs", 100))
        while len(self.job_order) > max_recent:
            old_id = self.job_order.pop(0)
            self.jobs.pop(old_id, None)

    def _deep_update(self, base: dict[str, Any], patch: dict[str, Any]) -> None:
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def _preserve_masked_secrets(self, patch: dict[str, Any], current: dict[str, Any]) -> None:
        for key, value in patch.items():
            if value == "***" and current.get(key):
                patch[key] = current[key]
            elif isinstance(value, dict) and isinstance(current.get(key), dict):
                self._preserve_masked_secrets(value, current[key])

    def _options_with_timeout(self, options: dict[str, Any] | None, timeout: float | None) -> dict[str, Any] | None:
        if timeout is None:
            return options
        merged = deepcopy(options or {})
        merged["timeout"] = float(timeout)
        return merged

    def _provider_timeout(self, job: LLMJob, provider_config: dict[str, Any], default: float) -> float:
        return max(1.0, float(job.options.get("timeout", provider_config.get("timeout", default))))
