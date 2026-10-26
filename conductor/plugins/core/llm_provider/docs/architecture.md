# LLM Provider Architecture

Core plugin ID: `llm_provider`

`llm_provider` is Conductor's shared queued LLM gateway. It provides one stable runtime for text generation, chat-style requests, vision-language requests, and embeddings, while keeping provider configuration, routing, concurrency control, and failure isolation inside the plugin itself.

This document is for maintainers of the plugin itself. If you are writing another plugin that wants to call `llm_provider`, see [plugin_api.md](./plugin_api.md).

## Goals

- Keep other plugins away from provider-specific client code.
- Route requests by semantic tier instead of hardcoded model names.
- Support both local `llama.cpp` models and OpenAI-compatible online providers.
- Prevent local model crashes from taking down the Conductor kernel.
- Enforce queueing and concurrency centrally.
- Expose a stable Python API, REST API, CLI surface, and Web UI.

## Module Layout

After the refactor, the plugin is intentionally split by responsibility instead of keeping everything inside `__init__.py`.

- [__init__.py](/Volumes/SSD/anti/Conductor/conductor/plugins/core/llm_provider/__init__.py): plugin lifecycle entrypoint. Defines `PLUGIN_METADATA`, creates the service in `on_load`, registers the blueprint, and tears the service down in `on_unload`.
- [service.py](/Volumes/SSD/anti/Conductor/conductor/plugins/core/llm_provider/service.py): the main runtime. Owns config loading, queueing, dispatch, routing, provider execution, tier selection, status reporting, and job lifecycle events.
- [local_runtime.py](/Volumes/SSD/anti/Conductor/conductor/plugins/core/llm_provider/local_runtime.py): isolated local `llama.cpp` executor. Runs local inference in a spawned subprocess so model crashes or hard hangs stay outside the kernel process.
- [api.py](/Volumes/SSD/anti/Conductor/conductor/plugins/core/llm_provider/api.py): Flask `/api/llm/*` routes. This file is only the HTTP adapter and delegates real behavior to the service.
- [commands.py](/Volumes/SSD/anti/Conductor/conductor/plugins/core/llm_provider/commands.py): CLI command registration for `!!conductor llm ...`.
- [registry.py](/Volumes/SSD/anti/Conductor/conductor/plugins/core/llm_provider/registry.py): module-level accessors such as `get_service()`, `complete()`, `chat()`, `embed()`, and `enqueue()`.
- [jobs.py](/Volumes/SSD/anti/Conductor/conductor/plugins/core/llm_provider/jobs.py): the `LLMJob` dataclass used by the queue and API responses.
- [constants.py](/Volumes/SSD/anti/Conductor/conductor/plugins/core/llm_provider/constants.py): plugin ID, default config skeleton, and tier aliases.
- [web/index.tsx](/Volumes/SSD/anti/Conductor/conductor/plugins/core/llm_provider/web/index.tsx): native WebApp management page.

## Runtime Flow

The runtime is centered on one long-lived `LLMProviderService` instance attached to `kernel.llm_provider`.

1. `on_load()` creates the service and registers `/api/llm`.
2. Callers enter through one of four surfaces:
   `kernel.llm_provider.*`, `from llm_provider import complete/chat/embed/enqueue`, `/api/llm/*`, and CLI commands in `commands.py`
3. `service.py` normalizes the request into an `LLMJob`.
4. The dispatcher thread selects a concrete target based on provider pinning or tier routing.
5. The selected provider runs:
   online providers execute in-process with `urllib.request`, while local `llama.cpp` providers execute in a spawned subprocess through `local_runtime.py`
6. The job is marked `succeeded` or `failed`, events are emitted, and waiting callers are released.

## Queue And Scheduling

The service uses an in-memory queue with capacity-aware dispatch.

- `_pending_jobs` stores queued jobs waiting for a runnable provider.
- `_running_jobs` tracks active worker threads per job.
- `_active_local_jobs` globally serializes all local `llama.cpp` execution to `1`.
- `_active_online_slots` tracks per-provider online concurrency.
- `_tier_round_robin` stores per-tier scheduling state for balanced routing.

The dispatcher does not simply pop FIFO and run blindly. It iterates pending jobs, checks whether each job currently has a provider with free capacity, reserves that slot, and only then starts a worker thread for that job.

This matters because:

- local inference is intentionally serialized
- online providers can have different `max_concurrency`
- tier-based routing may temporarily prefer one provider and later fall back to another

## Routing Model

Every configured provider belongs to a unified `providers` map. A request can resolve in two ways:

- Concrete provider mode: the caller passes `provider="some_provider_id"` and that exact provider must be enabled and available.
- Tier mode: the caller passes `tier="t1" | "t2" | "t3" | "vl" | "eb"` and the service selects a concrete provider from that tier.

Tier routing is governed by `config["routing"][tier]`:

- `default_provider`: preferred provider when it has free capacity
- `strategy="balanced"`: rotate among available providers in that tier
- `strategy="priority"`: choose the lowest-load provider in a stable order

Current selection preference is:

1. explicit provider if one was requested
2. tier `default_provider` if configured and available
3. another online provider in the same tier if available
4. a local provider in the same tier if online capacity is full and a local target is idle

## Provider Types

Two provider families are supported.

### `openai_compatible`

These run inside the main process through HTTP calls.

- Chat requests go to `/chat/completions`
- Embedding requests go to `/embeddings`
- Timeout is enforced through the HTTP client timeout
- Concurrency is per provider via `max_concurrency`

### `llama_cpp`

These run in a spawned subprocess instead of inside the kernel process.

- Chat and embeddings are both supported
- Vision-language requests are supported when the provider tier is `vl`
- Timeout is enforced by joining the subprocess with a deadline and then terminating or killing it if needed
- Concurrency is globally fixed at `1`

## Why `local_runtime.py` Exists

This split is not cosmetic; it fixes a real failure mode.

The previous implementation placed the local subprocess target inside the plugin entry module. Because Conductor loads plugins dynamically, that shape is brittle with Python `multiprocessing spawn`: child processes may fail to import the target correctly, and a healthy model can fail before inference even starts.

`local_runtime.py` fixes that by giving the subprocess a stable importable module-level target: `run_llama_cpp_subprocess`.

That module also provides:

- `_ensure_plugin_package_importable()`: makes sure the plugin package is importable in the child process
- `run_llama_cpp_request()`: parent-side wrapper that starts the child process, waits, enforces timeout, and collects results

## Timeout Model

Timeout now has two layers, both intentional.

- Caller wait timeout: `complete()`, `chat()`, and `embed()` still wait on `job.event` with the caller-provided `timeout`.
- Provider execution timeout: that same timeout is injected into `job.options["timeout"]`, so the actual online request or local subprocess enforces the same deadline while the job is running.

This fixes the earlier bug where a request could time out only from the caller's point of view while the real model execution kept running in the background.

## Config Model

Runtime config lives at:

```text
storage/config/llm_provider/config.json
```

The normalized top-level structure is:

```json
{
  "queue": {
    "max_recent_jobs": 100
  },
  "routing": {
    "t1": {"default_provider": "", "strategy": "balanced"},
    "t2": {"default_provider": "", "strategy": "balanced"},
    "t3": {"default_provider": "", "strategy": "balanced"},
    "vl": {"default_provider": "", "strategy": "balanced"},
    "eb": {"default_provider": "", "strategy": "balanced"}
  },
  "providers": {}
}
```

The service also removes stale keys from older designs during normalization:

- `default_provider`
- `default_system_prompt`
- `plugin_defaults`

That cleanup keeps old configs from silently dragging dead behavior forward.

## Local Model Assets

Local model files are discovered under:

```text
storage/data/llm_provider/models/
```

The service scans this directory and exposes:

- `models`: local `.gguf` / `.bin` model files
- `mmprojs`: likely projector files for VL models

The Web UI uses that scan to populate model selectors instead of requiring manual path entry every time.

## Vision-Language Notes

VL support is handled inside `service.py` before calling the local runtime.

- system messages may be folded into user text for some local handlers
- multimodal user messages are normalized into the handler-compatible shape
- `Qwen25VLChatHandler` currently prefers image parts before text parts

For local VL providers, the provider config must include both:

- `mmproj_path`
- `vl_handler`

Without those, the request may run as plain text or fail.

## Public Surfaces

The plugin intentionally offers the same core behavior through multiple adapters.

### Python Service

Attached to the kernel as `kernel.llm_provider`.

Key methods:

- `complete()`
- `chat()`
- `embed()`
- `enqueue()`
- `wait()`
- `status()`
- `get_job()`

### Module Helpers

Imported from `llm_provider` through `registry.py`.

- `get_service()`
- `complete()`
- `chat()`
- `embed()`
- `enqueue()`

### REST API

Implemented in `api.py`, mounted under `/api/llm`.

- `GET /status`
- `GET /providers`
- `POST|DELETE /providers/<provider_id>`
- `GET|POST /routing`
- `GET /models`
- `POST /complete`
- `POST /chat`
- `POST /embed`
- `POST /jobs`
- `GET /jobs/<job_id>`

### CLI

Implemented in `commands.py`.

- `!!conductor llm status`
- `!!conductor llm providers`
- `!!conductor llm complete <<prompt>>`

## Events

The service dispatches these events on the kernel event bus:

- `llm_provider.job_queued`
- `llm_provider.job_started`
- `llm_provider.job_completed`
- `llm_provider.job_failed`

Queued and started events include the request body; completion and failure events include result or error state for observers.

## Web UI Responsibilities

The Web UI is an operator console, not the source of truth.

It uses the REST API to:

- test requests
- inspect jobs
- manage provider definitions
- manage tier routing
- inspect the latest local runtime debug snapshot

Core queueing, routing, timeout, and failure isolation behavior remain in `service.py`.
