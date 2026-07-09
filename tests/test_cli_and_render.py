from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from clipscript.cli import app
from clipscript.engine import render_project
from clipscript.project import load_project
from clipscript.tts import TTSRegistry


def write_project(
    tmp_path: Path, *, voiceover: str | None = None, scene: dict[str, object] | None = None
) -> Path:
    template_path = tmp_path / "template.json"
    template_path.write_text(
        json.dumps({"resolution": [64, 96], "fps": 6, "fontFamily": "system"}), encoding="utf-8"
    )
    effective_scene = scene or {"type": "title", "duration": 0.5, "caption": "Offline"}
    if voiceover is not None:
        effective_scene["voiceover"] = voiceover
    script_path = tmp_path / "script.json"
    script_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "title": "Smoke",
                "output": "output/smoke.mp4",
                "template": "template.json",
                "scenes": [effective_scene],
            }
        ),
        encoding="utf-8",
    )
    return script_path


def test_validate_command_accepts_schema_v1_script(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["validate", "--input", str(write_project(tmp_path))])

    assert result.exit_code == 0, result.output
    assert "Script is valid" in result.output


class FailingProvider:
    name = "offline"

    def synthesize(self, text: str, request: object, output_path: Path) -> None:
        raise AssertionError("TTS must not run for scenes without voiceover")


@pytest.mark.smoke
def test_offline_render_writes_readable_mp4_without_tts(tmp_path: Path) -> None:
    project = load_project(str(write_project(tmp_path)))
    providers = TTSRegistry()
    providers.register(FailingProvider())
    output = tmp_path / "rendered.mp4"

    rendered = render_project(project, output_path=output, cache_dir=tmp_path / "cache", providers=providers)

    assert rendered == output
    assert output.is_file()
    assert output.read_bytes()[4:8] == b"ftyp"
    from moviepy import VideoFileClip

    clip = VideoFileClip(str(output))
    try:
        assert (clip.w, clip.h) == (64, 96)
        assert round(clip.fps) == 6
    finally:
        clip.close()


@pytest.mark.smoke
def test_video_duration_is_clamped_to_source_media(tmp_path: Path) -> None:
    from moviepy import ColorClip, VideoFileClip

    source_path = tmp_path / "source.mp4"
    source = ColorClip((64, 64), color=(0, 128, 255), duration=0.5)
    try:
        source.write_videofile(str(source_path), fps=6, codec="libx264", audio=False, logger=None)
    finally:
        source.close()
    project = load_project(
        str(write_project(tmp_path, scene={"type": "video", "src": "source.mp4", "duration": 2.0}))
    )
    output = tmp_path / "clamped.mp4"

    render_project(project, output_path=output, cache_dir=tmp_path / "cache")

    clip = VideoFileClip(str(output))
    try:
        assert 0.4 <= clip.duration <= 0.6
    finally:
        clip.close()
