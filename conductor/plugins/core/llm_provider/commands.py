from __future__ import annotations

from conductor.core.command.builder import SimpleCommandBuilder
from conductor.core.command.node import GreedyText
from conductor.core.permission import PermissionLevel

from .registry import get_service


def cmd_status(source, ctx):
    status = get_service().status()
    lines = [
        "--- LLM Provider ---",
        f"Queue size: {status['queue_size']}",
        f"Worker alive: {status['worker_alive']}",
        "Tiers: " + ", ".join(f"{tier}={meta.get('count', 0)}" for tier, meta in status.get("tiers", {}).items()),
        f"Providers: {', '.join(item.get('provider_id') or item.get('selector') for item in status.get('selectable_models', []))}",
    ]
    source.reply("\n".join(lines), "llm_provider")


def cmd_providers(source, ctx):
    status = get_service().status()
    lines = ["--- LLM Providers ---"]
    for item in status.get("selectable_models", []):
        lines.append(
            f"{item.get('provider_id') or item.get('selector')}: type={item.get('type')} transport={item.get('transport')} "
            f"tier={item.get('tier') or '-'} enabled={item.get('enabled', True)} model={item.get('model') or '-'}"
        )
    source.reply("\n".join(lines), "llm_provider")


def cmd_complete(source, ctx):
    prompt = " ".join(ctx.get("prompt", []))
    try:
        result = get_service().complete(prompt, plugin_id="console", tier="t2", timeout=120)
        source.reply(result.get("text", ""), "llm_provider")
    except Exception as exc:
        source.reply(f"LLM request failed: {exc}", "llm_provider")


def register_commands(kernel) -> None:
    builder = SimpleCommandBuilder()
    builder.arg("prompt", GreedyText)
    builder.command("!!conductor llm status", cmd_status, PermissionLevel.ADMIN, "Show LLM provider status", "llm_provider")
    builder.command("!!conductor llm providers", cmd_providers, PermissionLevel.ADMIN, "List LLM providers", "llm_provider")
    builder.command("!!conductor llm complete <<prompt>>", cmd_complete, PermissionLevel.ADMIN, "Run a one-shot LLM completion", "llm_provider")
    builder.register(kernel)
