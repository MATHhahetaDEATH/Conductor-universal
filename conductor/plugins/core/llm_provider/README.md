# LLM Provider

Shared queued access to local llama.cpp and OpenAI-compatible online providers.

- Route: `/llm_provider`
- API: `/api/llm/status`, `/providers`, `/routing`, `/models`, `/complete`,
  `/chat`, `/vision`, `/embed`, `/jobs`
- Configuration: `storage/config/llm_provider/config.json`
- Permissions: authenticated reads and inference; ADMIN for provider/routing writes.

Other plugins should call the registry helpers instead of creating their own LLM
runtime or provider configuration.
