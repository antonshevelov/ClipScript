from __future__ import annotations

from pathlib import Path

import pytest

from clipscript.renderers import default_renderer_registry
from clipscript.tts import TTSCache, TTSRegistry, TTSRequest


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, text: str, request: TTSRequest, output_path: Path) -> None:
        self.calls += 1
        output_path.write_bytes(f"{text}:{request.voice}".encode())


def test_default_renderer_registry_contains_all_scene_types() -> None:
    registry = default_renderer_registry()

    assert {registry.get(kind).scene_type for kind in ("chat", "title", "video", "outro")} == {
        "chat",
        "title",
        "video",
        "outro",
    }


def test_registry_rejects_duplicate_provider() -> None:
    registry = TTSRegistry()
    provider = FakeProvider()
    registry.register(provider)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(provider)


def test_tts_cache_is_atomic_and_uses_all_sound_parameters(tmp_path: Path) -> None:
    provider = FakeProvider()
    registry = TTSRegistry()
    registry.register(provider)
    cache = TTSCache(tmp_path, registry)
    first_request = TTSRequest(provider="fake", voice="voice-a", model_id="model-a")
    second_request = TTSRequest(provider="fake", voice="voice-b", model_id="model-a")

    first_path = cache.synthesize("Hello", first_request)
    cached_path = cache.synthesize("Hello", first_request)
    second_path = cache.synthesize("Hello", second_request)

    assert first_path == cached_path
    assert first_path != second_path
    assert provider.calls == 2
    assert first_path.read_bytes() == b"Hello:voice-a"
    assert not list(tmp_path.glob(".*.mp3"))
