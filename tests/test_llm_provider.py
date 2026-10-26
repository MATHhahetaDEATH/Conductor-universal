from __future__ import annotations

import logging

import pytest

from conductor.plugins.core.llm_provider.service import LLMProviderService


class FakeKernel:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.events = []

    def get_logger(self, name):
        return logging.getLogger(name)

    def get_plugin_config_dir(self, plugin_id):
        path = self.tmp_path / "config" / plugin_id
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def get_plugin_data_dir(self, plugin_id):
        path = self.tmp_path / "data" / plugin_id
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def dispatch_event(self, event_id, payload):
        self.events.append((event_id, payload))


@pytest.fixture
def service(tmp_path):
    instance = LLMProviderService(FakeKernel(tmp_path))
    yield instance
    instance.stop()


def test_timeout_is_passed_to_local_runtime(monkeypatch, service):
    observed = {}

    def fake_run_llama_cpp_request(**kwargs):
        observed.update(kwargs)
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
            "model": "fake",
        }

    monkeypatch.setattr("conductor.plugins.core.llm_provider.service.run_llama_cpp_request", fake_run_llama_cpp_request)
    service.upsert_provider(
        "local_test",
        {
            "type": "llama_cpp",
            "enabled": True,
            "model_path": "/tmp/fake.gguf",
            "tier": "t1",
        },
    )

    result = service.complete("hello", provider="local_test", timeout=7)

    assert result["text"] == "ok"
    assert observed["timeout_seconds"] == 7


def test_timeout_is_passed_to_online_runtime(monkeypatch, service):
    observed = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"ok"}}],"usage":{},"model":"remote"}'

    def fake_urlopen(req, timeout):
        observed["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    service.upsert_provider(
        "online_test",
        {
            "type": "openai_compatible",
            "enabled": True,
            "base_url": "https://example.test/v1",
            "model": "remote",
            "tier": "t1",
        },
    )

    result = service.complete("hello", provider="online_test", timeout=5)

    assert result["text"] == "ok"
    assert observed["timeout"] == 5


def test_local_runtime_worker_is_importable_from_plugin_package():
    import conductor.plugins.core.llm_provider.local_runtime as local_runtime

    assert local_runtime.run_llama_cpp_subprocess.__module__.endswith("llm_provider.local_runtime")


def test_vision_builds_multimodal_message(service):
    request_target, resolved_tier, options, messages, inputs = service._prepare_request(
        plugin_id="my_plugin",
        prompt="Describe this image.",
        messages=None,
        images=["https://example.com/example.png"],
        inputs=None,
        system_prompt="Be concise.",
        provider=None,
        tier="vl",
        options=None,
    )

    assert request_target is None
    assert resolved_tier == "vl"
    assert inputs == []
    assert messages == [
        {"role": "system", "content": "Be concise."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image."},
                {"type": "image_url", "image_url": {"url": "https://example.com/example.png"}},
            ],
        },
    ]


def test_images_require_vl_tier(service):
    with pytest.raises(ValueError, match="tier='vl'"):
        service._prepare_request(
            plugin_id="my_plugin",
            prompt="Describe this image.",
            messages=None,
            images=["https://example.com/example.png"],
            inputs=None,
            system_prompt=None,
            provider=None,
            tier="t2",
            options=None,
        )
