"""Extensible TTS providers and an atomic on-disk audio cache."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Protocol

import edge_tts
import requests

from clipscript.models import TemplateConfig


@dataclass(frozen=True)
class TTSRequest:
    provider: str
    voice: str
    voice_id: str | None = None
    model_id: str | None = None
    output_format: str = "mp3_44100_128"
    voice_settings: dict[str, float | bool] = field(
        default_factory=lambda: {
            "stability": 0.5,
            "similarity_boost": 0.5,
            "style": 0.0,
            "use_speaker_boost": True,
        }
    )

    def cache_payload(self, text: str) -> bytes:
        return json.dumps(
            {"text": text, "request": asdict(self)},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, request: TTSRequest, output_path: Path) -> None:
        """Write encoded audio to ``output_path``."""


class TTSGenerationError(RuntimeError):
    """A provider failure that can be shown safely at the CLI boundary."""


class TTSRegistry:
    """Maps configured provider names to independently testable implementations."""

    def __init__(self) -> None:
        self._providers: dict[str, TTSProvider] = {}

    def register(self, provider: TTSProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"TTS provider already registered: '{provider.name}'")
        self._providers[provider.name] = provider

    def get(self, name: str) -> TTSProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise ValueError(f"no TTS provider registered for '{name}'") from exc


class EdgeTTSProvider:
    name = "edge"

    async def _save(self, text: str, voice: str, output_path: Path) -> None:
        await edge_tts.Communicate(text, voice).save(str(output_path))

    def synthesize(self, text: str, request: TTSRequest, output_path: Path) -> None:
        asyncio.run(self._save(text, request.voice, output_path))


class ElevenLabsTTSProvider:
    name = "elevenlabs"
    temporary_statuses = frozenset({429, 500, 502, 503, 504})

    def __init__(
        self,
        retries: int = 3,
        timeout_seconds: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._retries = retries
        self._timeout_seconds = timeout_seconds
        self._sleep = sleep

    def synthesize(self, text: str, request: TTSRequest, output_path: Path) -> None:
        if not request.voice_id:
            raise ValueError("voice_id is required for the elevenlabs provider")
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY is required for the elevenlabs provider")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{request.voice_id}"
        payload = {
            "text": text,
            "model_id": request.model_id,
            "voice_settings": request.voice_settings,
        }
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": api_key}
        last_status: int | None = None
        for attempt in range(self._retries + 1):
            response: requests.Response | None = None
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    params={"output_format": request.output_format},
                    timeout=self._timeout_seconds,
                )
                last_status = response.status_code
                if response.status_code == 200:
                    output_path.write_bytes(response.content)
                    return
                retryable = response.status_code in self.temporary_statuses
            except requests.RequestException:
                retryable = True
            finally:
                if response is not None:
                    response.close()
            if not retryable or attempt == self._retries:
                break
            self._sleep(0.5 * (2**attempt))
        status_text = str(last_status) if last_status is not None else "network error"
        raise RuntimeError(
            f"ElevenLabs request failed after {self._retries + 1} attempts ({status_text})"
        )


class TTSCache:
    """Cache provider output using SHA-256 keys and atomic replacements."""

    def __init__(self, cache_dir: Path, providers: TTSRegistry) -> None:
        self._cache_dir = cache_dir
        self._providers = providers

    def key_for(self, text: str, request: TTSRequest) -> str:
        return hashlib.sha256(request.cache_payload(text)).hexdigest()

    def synthesize(self, text: str, request: TTSRequest) -> Path:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_dir / f"{self.key_for(text, request)}.mp3"
        if cache_path.is_file() and cache_path.stat().st_size > 0:
            return cache_path

        temporary_path = self._cache_dir / f".{cache_path.stem}.{uuid.uuid4().hex}.mp3"
        try:
            try:
                self._providers.get(request.provider).synthesize(text, request, temporary_path)
            except Exception as exc:
                raise TTSGenerationError(
                    f"TTS provider '{request.provider}' failed; check provider settings and network access"
                ) from exc
            if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
                raise TTSGenerationError(f"TTS provider '{request.provider}' produced no audio")
            os.replace(temporary_path, cache_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return cache_path


def request_from_template(template: TemplateConfig) -> TTSRequest:
    voice_id = template.voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
    return TTSRequest(
        provider=template.ttsProvider,
        voice=template.voice,
        voice_id=voice_id,
        model_id=template.elevenlabsModelId,
    )


def default_tts_registry() -> TTSRegistry:
    registry = TTSRegistry()
    registry.register(EdgeTTSProvider())
    registry.register(ElevenLabsTTSProvider())
    return registry


def list_voices(provider: str) -> list[str]:
    """List provider voices with provider-specific configuration and error messages."""
    try:
        if provider == "edge":
            edge_voices = asyncio.run(edge_tts.list_voices())
            return sorted(str(voice["ShortName"]) for voice in edge_voices if "ShortName" in voice)
        if provider == "elevenlabs":
            api_key = os.environ.get("ELEVENLABS_API_KEY")
            if not api_key:
                raise TTSGenerationError("ELEVENLABS_API_KEY is required for the elevenlabs provider")
            response = requests.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": api_key},
                timeout=20.0,
            )
            try:
                response.raise_for_status()
                payload = response.json()
            finally:
                response.close()
            entries = payload.get("voices", [])
            if not isinstance(entries, list):
                raise TTSGenerationError("ElevenLabs returned an invalid voices response")
            return sorted(
                str(entry.get("name"))
                for entry in entries
                if isinstance(entry, dict) and isinstance(entry.get("name"), str)
            )
    except TTSGenerationError:
        raise
    except Exception as exc:
        # Provider clients expose several async transport exception classes.
        raise TTSGenerationError(
            f"could not list {provider} voices; check network access and provider configuration"
        ) from exc
    raise TTSGenerationError("provider must be edge or elevenlabs")
