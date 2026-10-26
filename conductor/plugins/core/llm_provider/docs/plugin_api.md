# LLM Provider Plugin API

Core plugin ID: `llm_provider`

This document is for authors of other Conductor plugins that want to call `llm_provider`. If you want to understand the internal implementation of the plugin itself, see [architecture.md](./architecture.md).

## Dependency Declaration

Your plugin should declare `llm_provider` as a dependency so the kernel loads it first.

```python
PLUGIN_METADATA = {
    "id": "my_plugin",
    "dependencies": ["llm_provider"],
}
```

After that, use `kernel.llm_provider` inside your plugin code.

## Main Entry Points

You will usually use one of these methods:

- `kernel.llm_provider.complete(...)`
- `kernel.llm_provider.chat(...)`
- `kernel.llm_provider.vision(...)`
- `kernel.llm_provider.embed(...)`
- `kernel.llm_provider.enqueue(...)`

The first four are synchronous helpers built on top of the same queue. `enqueue()` is the asynchronous form and returns a `job_id`.

## Tier-First Calling Strategy

The recommended pattern is to request by tier, not by concrete provider ID.

Available tiers:

- `t1`: 1B-8B text models
- `t2`: 9B+ general text models
- `t3`: larger or flagship text models
- `vl`: vision-language models
- `eb`: embedding models

When you call by tier, `llm_provider` chooses a concrete configured model for you according to the operator's routing settings.

This is the main contract:

- your plugin expresses capability needs
- the operator decides which actual models satisfy those needs

That keeps your plugin portable across deployments.

## When To Use Each Tier

### `t1`

Use `t1` for cheap or frequent text tasks where latency matters more than absolute model strength.

Examples:

- lightweight extraction
- simple classification
- short summaries
- batch preprocessing

### `t2`

Use `t2` for the default “good general model” path.

Examples:

- most summarization
- structured extraction with moderate complexity
- rewriting and transformation
- ordinary plugin-facing assistant behavior

If you are unsure which text tier to choose, `t2` is usually the safest default.

### `t3`

Use `t3` when the task is materially harder and you want the deployment to prefer larger or stronger models.

Examples:

- harder reasoning or synthesis
- longer, more delicate generation tasks
- extraction where accuracy matters more than cost

Do not use `t3` automatically for everything; it is meant to signal genuinely higher capability needs.

### `vl`

Use `vl` only for requests that include image input or require a vision-language model.

Call through `vision()`.

### `eb`

Use `eb` only for embeddings.

Call through `embed()`, not `complete()` or `chat()`.

## `complete()` Usage

`complete()` is the simplest one-shot text interface.

```python
result = kernel.llm_provider.complete(
    "Summarize this content.",
    plugin_id="my_plugin",
    system_prompt="You are a concise analyst.",
    tier="t2",
    options={"temperature": 0.2, "max_tokens": 300},
    timeout=120,
)
text = result["text"]
```

Use `complete()` when:

- you have one plain user prompt
- you want an optional system prompt
- you do not need to build a full message list yourself

## `chat()` Usage

`chat()` accepts an explicit message list. Use it when your plugin already manages its own prompt structure or conversation history.

```python
result = kernel.llm_provider.chat(
    [
        {"role": "system", "content": "You extract entities into JSON."},
        {"role": "user", "content": "Analyze this document."},
    ],
    plugin_id="my_plugin",
    tier="t2",
    options={"temperature": 0.1, "max_tokens": 500},
    timeout=120,
)
text = result["text"]
```

Use `chat()` when:

- you already have a message list
- you want explicit control over roles and history

## `embed()` Usage

`embed()` is only for embedding models and normally targets `tier="eb"`.

Single string:

```python
result = kernel.llm_provider.embed(
    "hello world",
    plugin_id="my_plugin",
    tier="eb",
    timeout=120,
)
vector = result["embeddings"][0]
```

Multiple strings:

```python
result = kernel.llm_provider.embed(
    ["first text", "second text"],
    plugin_id="my_plugin",
    tier="eb",
    timeout=120,
)
vectors = result["embeddings"]
```

## `vision()` Usage

`vision()` is the high-level interface for image + prompt requests.

Single image:

```python
result = kernel.llm_provider.vision(
    prompt="Describe this image.",
    images="https://example.com/example.png",
    plugin_id="my_plugin",
    tier="vl",
    timeout=120,
)
text = result["text"]
```

Multiple images:

```python
result = kernel.llm_provider.vision(
    prompt="Compare these images and summarize the differences.",
    images=[
        "https://example.com/one.png",
        "https://example.com/two.png",
    ],
    plugin_id="my_plugin",
    tier="vl",
    timeout=120,
)
text = result["text"]
```

Use `vision()` when:

- your input is one or more images plus a prompt
- you want `llm_provider` to handle the underlying multimodal request shape for you
- you want the same simple calling style regardless of which concrete VL provider is configured underneath

## `enqueue()` Usage

`enqueue()` submits a job and returns immediately.

Text job:

```python
job_id = kernel.llm_provider.enqueue(
    plugin_id="my_plugin",
    prompt="Analyze this item.",
    tier="t1",
    options={"max_tokens": 256},
)
```

Vision job:

```python
job_id = kernel.llm_provider.enqueue(
    plugin_id="my_plugin",
    prompt="Describe this image.",
    images="https://example.com/example.png",
    tier="vl",
)
```

Use this when:

- you do not want to block the current flow
- you plan to poll `get_job()` later
- you want queue semantics without synchronous waiting

## Concrete Provider Pinning

Sometimes a plugin really does need a specific configured provider. That is supported through `provider=...`.

```python
result = kernel.llm_provider.complete(
    "Summarize this content.",
    plugin_id="my_plugin",
    provider="qwen3_235b_api",
    timeout=120,
)
```

Use provider pinning sparingly. It ties your plugin to operator-specific configuration and makes deployments less portable than tier-based routing.

## Tier-Specific Calling Details

### Text Tiers: `t1`, `t2`, `t3`

For text tiers, both `complete()` and `chat()` are valid.

Recommended defaults:

- prefer `complete()` for one-shot prompt-in, text-out tasks
- prefer `chat()` when you already maintain a structured message list
- start with `t2` unless you have a reason to bias smaller or larger

### Vision Tier: `vl`

For `vl`, call `vision()` and pass a prompt plus one or more image URLs.

```python
result = kernel.llm_provider.vision(
    prompt="Describe this image.",
    images="https://example.com/example.png",
    plugin_id="my_plugin",
    tier="vl",
    timeout=120,
)
text = result["text"]
```

Important details:

- `vl` requests should go through `vision()`, not `complete()`
- pass `images=` as either one URL string or a list of URL strings
- `llm_provider` is responsible for turning that simple input into the provider-specific multimodal request shape

If your request is actually text-only, do not use `vl`; use `t1`, `t2`, or `t3`.

### Embedding Tier: `eb`

For `eb`, call `embed()`.

Important details:

- `embed()` accepts either a string or a list of strings
- the return value is `result["embeddings"]`
- do not use `complete()` or `chat()` for embedding work

## `plugin_id` Meaning

Always pass your own plugin ID in `plugin_id=...`.

```python
plugin_id="my_plugin"
```

That value is used for job metadata, logging, and debugging. It helps operators understand which plugin generated a given request.

## Timeout Semantics

`timeout` should be treated as the real execution deadline for the request.

```python
result = kernel.llm_provider.complete(
    "Summarize this content.",
    plugin_id="my_plugin",
    tier="t2",
    timeout=90,
)
```

This timeout is applied in two places:

- your caller waits up to that many seconds
- the underlying provider execution also uses that timeout

That means a timeout is not just “the caller gave up waiting”; it is intended to stop the actual model work as well.

## `options` Semantics

`options` overrides provider defaults for one request.

Common fields:

- `temperature`
- `max_tokens`
- `top_p`
- `presence_penalty`
- `frequency_penalty`
- `stop`
- `model`
- `timeout`

Example:

```python
result = kernel.llm_provider.complete(
    "Rewrite this paragraph.",
    plugin_id="my_plugin",
    tier="t2",
    options={
        "temperature": 0.3,
        "max_tokens": 400,
    },
    timeout=120,
)
```

For most plugin code, prefer passing `timeout` as the dedicated argument and sampling/generation controls inside `options`.

## Return Shapes

Text generation and chat return a dictionary like:

```json
{
  "text": "model response",
  "provider": "qwen3_235b_api",
  "selector": "qwen3_235b_api",
  "tier": "t3",
  "model": "qwen3-235b",
  "usage": {},
  "raw": {}
}
```

Embedding returns a dictionary like:

```json
{
  "embeddings": [[0.1, 0.2], [0.3, 0.4]],
  "provider": "bge_m3_api",
  "selector": "bge_m3_api",
  "tier": "eb",
  "model": "bge-m3",
  "usage": {},
  "raw": {}
}
```

Useful fields:

- `text`: final text output for generation/chat
- `embeddings`: embedding vectors for `embed()`
- `provider`: configured provider ID that actually ran
- `tier`: tier requested or resolved
- `raw`: original provider payload for debugging

## Failure Behavior

If a request fails:

- synchronous helpers raise an exception
- asynchronous jobs move to `failed`
- local `llama.cpp` crashes or hangs should be isolated from the kernel process

Typical failure causes:

- unknown provider or tier
- disabled provider
- no provider in the requested tier
- missing online credentials
- local `llama-cpp-python` not installed
- execution timeout

## Practical Recommendations

- Prefer `tier="t2"` for general text work.
- Prefer `tier="t1"` for cheap repetitive tasks.
- Reserve `tier="t3"` for genuinely harder tasks.
- Use `tier="vl"` only when there is image input.
- Use `tier="eb"` only with `embed()`.
- Pass `plugin_id` truthfully.
- Keep prompts deterministic when you want machine-readable output.
- Use provider pinning only when portability is not important.
