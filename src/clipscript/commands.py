"""Filesystem and diagnostics helpers used by the CLI commands."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg

from clipscript.models import ScriptConfig
from clipscript.project import ProjectError


def effective_cache_dir() -> Path:
    return Path(os.environ.get("CLIPSCRIPT_CACHE_DIR", Path.cwd() / ".clipscript" / "cache" / "tts"))


def initialize_project(target: Path, force: bool) -> Path:
    """Write a small Schema v2 project which renders without a network provider."""
    if target.exists() and any(target.iterdir()) and not force:
        raise ProjectError(f"'{target}' is not empty; use --force to replace starter files")
    target.mkdir(parents=True, exist_ok=True)
    assets = target / "assets"
    assets.mkdir(exist_ok=True)
    template = target / "template.json"
    script = target / "script.json"
    if (template.exists() or script.exists()) and not force:
        raise ProjectError("starter files already exist; use --force to replace them")
    template.write_text(
        json.dumps({"resolution": [540, 960], "fps": 24, "fontFamily": "system"}, indent=2) + "\n",
        encoding="utf-8",
    )
    script.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "title": "ClipScript starter",
                "output": "output/starter.mp4",
                "template": "template.json",
                "scenes": [
                    {"type": "title", "duration": 1.5, "caption": "ClipScript v0.2"},
                    {"type": "outro", "duration": 1.5, "caption": "Edit script.json to begin"},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return script


def doctor_checks() -> list[tuple[str, bool, str]]:
    """Check local prerequisites only; no TTS provider request is made."""
    checks: list[tuple[str, bool, str]] = []
    supported = (3, 9) <= sys.version_info[:2] <= (3, 12)
    checks.append(("Python", supported, f"{sys.version.split()[0]} (supported: 3.9-3.12)"))
    try:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        checks.append(("FFmpeg", Path(ffmpeg).is_file(), ffmpeg))
    except Exception as exc:  # pragma: no cover - depends on broken local installation.
        checks.append(("FFmpeg", False, str(exc)))
    try:
        with tempfile.NamedTemporaryFile(prefix="clipscript-doctor-", delete=True):
            pass
        checks.append(("Temporary directory", True, tempfile.gettempdir()))
    except OSError as exc:
        checks.append(("Temporary directory", False, str(exc)))
    cache = effective_cache_dir()
    try:
        cache.mkdir(parents=True, exist_ok=True)
        probe = cache / ".doctor-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(("TTS cache", True, str(cache)))
    except OSError as exc:
        checks.append(("TTS cache", False, str(exc)))
    eleven = bool(os.environ.get("ELEVENLABS_API_KEY"))
    checks.append(("ElevenLabs configuration", eleven, "API key found" if eleven else "API key not set"))
    checks.append(("Edge configuration", True, "uses network only when generating or listing voices"))
    return checks


def clear_cache(yes: bool) -> int:
    cache = effective_cache_dir()
    if not yes:
        raise ProjectError("cache clear requires --yes")
    if not cache.exists():
        return 0
    if cache.name != "tts" or not any(part in {"clipscript", ".clipscript"} for part in cache.parts):
        raise ProjectError("refusing to clear a cache path outside ClipScript's TTS cache")
    shutil.rmtree(cache)
    return 0


def schema_json() -> str:
    return json.dumps(ScriptConfig.model_json_schema(by_alias=True), ensure_ascii=False, indent=2) + "\n"
