from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from clipscript import media
from clipscript.cli import app
from clipscript.engine import render_project, validate_project_references
from clipscript.models import ChatScene, TemplateConfig
from clipscript.project import ProjectError, load_project, parse_script
from clipscript.renderers import RenderContext, draw_chat_frame, get_system_font
from clipscript.subtitles import SubtitleCue, plan_subtitles, write_srt
from clipscript.timeline import plan_chat_timeline, resolved_side
from clipscript.tts import TTSGenerationError, list_voices


def v2_script(scenes: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "title": "V2",
        "output": "output/result.mp4",
        "template": "template.json",
        "scenes": scenes,
    }


def write_project(tmp_path: Path, scenes: list[dict[str, object]], subtitles: object = None) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "template.json").write_text(
        json.dumps({"resolution": [64, 96], "fps": 6, "fontFamily": "system"}), encoding="utf-8"
    )
    payload = v2_script(scenes)
    if subtitles is not None:
        payload["subtitles"] = subtitles
    script = tmp_path / "script.json"
    script.write_text(json.dumps(payload), encoding="utf-8")
    return script


def test_v1_chat_normalizes_and_retains_legacy_auto_timing() -> None:
    config = parse_script(
        {
            "schemaVersion": 1,
            "title": "V1",
            "output": "out.mp4",
            "template": "template.json",
            "scenes": [{"type": "chat", "duration": 2.0, "messages": ["one", "two"]}],
        }
    )
    chat = config.scenes[0]
    assert isinstance(chat, ChatScene)
    timeline = plan_chat_timeline(chat, 2.0)

    assert config.schema_version == 2
    assert [message.appears_at for message in timeline] == [0.2, 1.5]
    assert [resolved_side(index, message.side) for index, message in enumerate(timeline)] == ["left", "right"]


def test_structured_chat_timing_typing_and_validation() -> None:
    config = parse_script(
        v2_script(
            [
                {
                    "type": "chat",
                    "duration": 3.0,
                    "messages": [
                        {"text": "First", "side": "right", "author": "A", "at": 1.0, "typing": 0.5},
                        {"text": "Second", "pause": 0.2, "at": 2.0},
                    ],
                }
            ]
        )
    )
    chat = config.scenes[0]
    assert isinstance(chat, ChatScene)
    timeline = plan_chat_timeline(chat, 3.0)

    assert timeline[0].is_typing(0.5)
    assert not timeline[0].is_visible(0.9)
    assert timeline[0].is_visible(1.0)
    assert timeline[0].side == "right"
    invalid = v2_script(
        [{"type": "chat", "duration": 2.0, "messages": [{"text": "late", "at": 1.5}, {"text": "early", "at": 1.0}]}]
    )
    with pytest.raises(ProjectError, match="monotonic"):
        parse_script(invalid)


@pytest.mark.parametrize(
    ("messages", "message"),
    [
        (
            [
                {"text": "First", "at": 0.5, "pause": 0.7},
                {"text": "Conflicts", "at": 1.0},
            ],
            "previous pause",
        ),
        (
                [
                    {"text": "First", "at": 1.0},
                    {"text": "Implicit", "typing": 0.4},
                ],
            "strictly before scene duration",
        ),
        ([{"text": "Too late", "at": 1.0, "pause": 0.3}], "pause extends beyond"),
        ([{"text": "Early", "at": 0.2, "typing": 0.3}], "typing cannot begin"),
    ],
)
def test_chat_validation_uses_resolved_schedule(
    messages: list[dict[str, object]], message: str
) -> None:
    data = v2_script([{"type": "chat", "duration": 1.2, "messages": messages}])

    with pytest.raises(ProjectError, match=message):
        parse_script(data)


def test_chat_pause_delays_the_next_implicit_message() -> None:
    chat = parse_script(
        v2_script(
            [
                {
                    "type": "chat",
                    "duration": 2.0,
                    "messages": [
                        {"text": "First", "at": 0.5, "pause": 0.4},
                        {"text": "Second", "author": "You", "side": "right"},
                    ],
                }
            ]
        )
    ).scenes[0]
    assert isinstance(chat, ChatScene)

    timeline = plan_chat_timeline(chat, 2.0)

    assert [message.appears_at for message in timeline] == [0.5, 0.9]
    assert timeline[1].author == "You"


def test_v2_chat_uses_author_not_sender() -> None:
    valid = v2_script(
        [{"type": "chat", "duration": 1.0, "messages": [{"text": "Hello", "author": "Marta"}]}]
    )
    chat = parse_script(valid).scenes[0]
    assert isinstance(chat, ChatScene)
    assert chat.messages and not isinstance(chat.messages[0], str)
    assert chat.messages[0].author == "Marta"

    invalid = v2_script(
        [{"type": "chat", "duration": 1.0, "messages": [{"text": "Hello", "sender": "Marta"}]}]
    )
    with pytest.raises(ProjectError, match="sender"):
        parse_script(invalid)


def test_chat_rejects_appearance_at_scene_duration() -> None:
    data = v2_script(
        [{"type": "chat", "duration": 1.0, "messages": [{"text": "Too late", "at": 1.0}]}]
    )

    with pytest.raises(ProjectError, match="strictly before scene duration"):
        parse_script(data)


def test_chat_typing_changes_the_drawn_frame() -> None:
    chat = parse_script(
        v2_script(
            [
                {
                    "type": "chat",
                    "duration": 2.0,
                    "messages": [{"text": "Ready", "at": 1.0, "typing": 0.5}],
                }
            ]
        )
    ).scenes[0]
    assert isinstance(chat, ChatScene)
    template = TemplateConfig(resolution=[96, 144], fps=6, fontFamily="system")
    tracker = media.ClipTracker()
    context = RenderContext(
        template=template,
        script_dir=Path.cwd(),
        template_dir=Path.cwd(),
        font_regular=get_system_font("system", 12),
        font_bold=get_system_font("system", 14),
        caption_font=get_system_font("system", 12),
        clips=tracker,
    )
    try:
        before = draw_chat_frame(0.2, chat, context, 2.0)
        typing = draw_chat_frame(0.7, chat, context, 2.0)
        visible = draw_chat_frame(1.1, chat, context, 2.0)
    finally:
        tracker.close_all()

    assert not np.array_equal(before, typing)
    assert not np.array_equal(typing, visible)


def test_chat_author_labels_render_for_both_sides_and_respect_sender_names() -> None:
    template = TemplateConfig(resolution=[160, 240], fps=6, fontFamily="system")
    tracker = media.ClipTracker()
    context = RenderContext(
        template=template,
        script_dir=Path.cwd(),
        template_dir=Path.cwd(),
        font_regular=get_system_font("system", 16),
        font_bold=get_system_font("system", 18),
        caption_font=get_system_font("system", 16),
        clips=tracker,
    )

    def frame(author: str, side: str, sender_names: bool) -> np.ndarray[tuple[int, ...], np.dtype[np.uint8]]:
        chat = parse_script(
            v2_script(
                [
                    {
                        "type": "chat",
                        "duration": 1.0,
                        "chatHeader": False,
                        "senderNames": sender_names,
                        "messages": [{"text": "Same text", "author": author, "side": side, "at": 0.1}],
                    }
                ]
            )
        ).scenes[0]
        assert isinstance(chat, ChatScene)
        return draw_chat_frame(0.5, chat, context, 1.0)

    try:
        left_marta = frame("Marta", "left", True)
        left_olena = frame("Olena", "left", True)
        right_marta = frame("Marta", "right", True)
        right_olena = frame("Olena", "right", True)
        hidden_marta = frame("Marta", "right", False)
        hidden_olena = frame("Olena", "right", False)
    finally:
        tracker.close_all()

    assert not np.array_equal(left_marta, left_olena)
    assert not np.array_equal(right_marta, right_olena)
    assert np.array_equal(hidden_marta, hidden_olena)


def test_v2_image_errors_and_contain_cover_render(tmp_path: Path) -> None:
    bad = tmp_path / "bad.png"
    bad.write_text("not an image", encoding="utf-8")
    script = write_project(tmp_path, [{"type": "image", "src": "bad.png", "duration": 1.0}])
    with pytest.raises(ValueError, match="corrupt"):
        validate_project_references(load_project(str(script)))

    from PIL import Image

    Image.new("RGB", (20, 10), "#ff0000").save(tmp_path / "image.png")
    script = write_project(
        tmp_path,
        [
            {"type": "image", "src": "image.png", "duration": 0.5, "fit": "contain"},
            {"type": "image", "src": "image.png", "duration": 0.5, "fit": "cover"},
        ],
    )
    output = tmp_path / "image.mp4"
    render_project(load_project(str(script)), output_path=output)
    assert output.is_file() and output.stat().st_size > 100
    from moviepy import VideoFileClip

    clip = VideoFileClip(str(output))
    try:
        contain_corner = clip.get_frame(0.1)[0, 0]
        cover_corner = clip.get_frame(0.6)[0, 0]
    finally:
        clip.close()
    assert int(contain_corner[1]) > 200
    assert int(cover_corner[0]) > 200 and int(cover_corner[1]) < 40


def test_fade_subtitles_and_cli_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = write_project(
        tmp_path,
        [
            {"type": "title", "duration": 1.0, "caption": "One", "subtitle": "Привіт"},
            {
                "type": "outro",
                "duration": 1.0,
                "caption": "Two",
                "subtitle": "Світ",
                "transition": {"type": "fade", "duration": 0.4},
            },
        ],
        {"mode": "both"},
    )
    output = tmp_path / "fade.mp4"
    render_project(load_project(str(script)), output_path=output)
    srt = output.with_suffix(".srt")
    assert "00:00:00,600 --> 00:00:01,600" in srt.read_text(encoding="utf-8")
    from moviepy import VideoFileClip

    clip = VideoFileClip(str(output))
    try:
        assert clip.duration == pytest.approx(10 / 6, abs=0.02)
        assert clip.get_frame(0.1).mean() > 0
    finally:
        clip.close()
    runner = CliRunner()
    initialized = tmp_path / "starter"
    assert runner.invoke(app, ["init", str(initialized)]).exit_code == 0
    assert runner.invoke(app, ["schema", "--output", str(tmp_path / "schema.json")]).exit_code == 0
    monkeypatch.setenv("CLIPSCRIPT_CACHE_DIR", str(tmp_path / ".clipscript" / "cache" / "tts"))
    cache = tmp_path / ".clipscript" / "cache" / "tts"
    cache.mkdir(parents=True)
    (cache / "voice.mp3").write_bytes(b"audio")
    assert runner.invoke(app, ["cache", "clear", "--yes"]).exit_code == 0
    assert not cache.exists()
    assert runner.invoke(app, ["doctor"]).exit_code == 0
    monkeypatch.setattr("clipscript.cli.list_voices", lambda provider: ["Mock voice"])
    assert "Mock voice" in runner.invoke(app, ["voices", "--provider", "edge"]).output
    preview_script = write_project(tmp_path / "preview", [{"type": "title", "duration": 0.5, "caption": "Draft"}])
    preview = runner.invoke(app, ["preview", "--input", str(preview_script)])
    assert preview.exit_code == 0
    assert (preview_script.parent / "output" / "preview.mp4").is_file()


def test_fade_blends_frames_and_uses_logical_overlap() -> None:
    from moviepy import AudioClip, ColorClip

    first_audio = AudioClip(lambda timestamp: 0.2, duration=1.0, fps=8000)
    second_audio = AudioClip(lambda timestamp: 0.4, duration=1.0, fps=8000)
    first = ColorClip((8, 8), color=(255, 0, 0), duration=1.0).with_audio(first_audio)
    second = ColorClip((8, 8), color=(0, 0, 255), duration=1.0).with_audio(second_audio)
    try:
        final = media.concatenate([first, second], [0.0, 0.4])
        frame = final.get_frame(0.8)
        audio = final.audio.get_frame(0.8)
        assert media.duration(final) == pytest.approx(1.6)
        assert 60 < int(frame[0, 0, 0]) < 200
        assert 60 < int(frame[0, 0, 2]) < 200
        assert float(np.asarray(audio).mean()) == pytest.approx(0.3)
    finally:
        final.close()
        first.close()
        second.close()
        first_audio.close()
        second_audio.close()


def test_srt_writer_is_utf8_and_overlap_aware(tmp_path: Path) -> None:
    cues = [SubtitleCue(0.0, 0.6, "Привіт"), SubtitleCue(0.6, 1.2, "world")]
    output = write_srt(cues, tmp_path / "captions.srt")
    assert output.read_text(encoding="utf-8").startswith(
        "1\n00:00:00,000 --> 00:00:00,600\n\u041f\u0440\u0438\u0432\u0456\u0442"
    )
    assert plan_subtitles([], [], []) == []


def test_schema_stdout_is_machine_readable_json() -> None:
    result = CliRunner().invoke(app, ["schema"])

    assert result.exit_code == 0, result.output
    schema = json.loads(result.output)
    assert schema["properties"]["schemaVersion"]["const"] == 2
    assert "ChatMessage" in schema["$defs"]


def test_init_rejects_a_file_target(tmp_path: Path) -> None:
    target = tmp_path / "not-a-directory"
    target.write_text("file", encoding="utf-8")
    runner = CliRunner()

    for arguments in (["init", str(target)], ["init", str(target), "--force"]):
        result = runner.invoke(app, arguments)
        assert result.exit_code == 1
        assert "not a directory" in " ".join(result.output.split())


def test_edge_voice_errors_are_user_facing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail() -> list[object]:
        raise RuntimeError("network unavailable")

    monkeypatch.setattr("clipscript.tts.edge_tts.list_voices", fail)
    with pytest.raises(TTSGenerationError, match="could not list edge voices"):
        list_voices("edge")
    monkeypatch.setattr("clipscript.cli.list_voices", lambda provider: list_voices(provider))
    result = CliRunner().invoke(app, ["voices", "--provider", "edge"])
    assert result.exit_code == 1
    assert "Voice lookup failed" in result.output
    assert "Traceback" not in result.output


def test_preview_even_dimensions_and_isolated_srt_output(tmp_path: Path) -> None:
    production_srt = tmp_path / "production.srt"
    production_srt.write_text("preserve", encoding="utf-8")
    script = write_project(
        tmp_path,
        [{"type": "title", "duration": 0.5, "caption": "Draft", "subtitle": "Caption"}],
        {"mode": "srt", "output": "production.srt"},
    )
    (tmp_path / "template.json").write_text(
        json.dumps({"resolution": [65, 97], "fps": 6, "fontFamily": "system"}), encoding="utf-8"
    )
    result = CliRunner().invoke(app, ["preview", "--input", str(script)])

    assert result.exit_code == 0, result.output
    from moviepy import VideoFileClip

    preview = VideoFileClip(str(tmp_path / "output" / "preview.mp4"))
    try:
        assert preview.w >= 2 and preview.h >= 2
        assert preview.w % 2 == 0 and preview.h % 2 == 0
    finally:
        preview.close()
    assert production_srt.read_text(encoding="utf-8") == "preserve"
    assert (tmp_path / "output" / "preview.srt").is_file()


def test_audio_mixing_applies_source_and_voiceover_volume() -> None:
    from moviepy import AudioClip

    source = AudioClip(lambda timestamp: 0.2, duration=0.5, fps=8000)
    voiceover = AudioClip(lambda timestamp: 0.4, duration=0.5, fps=8000)
    try:
        mixed = media.mix_audio([media.volume(source, 0.5), media.volume(voiceover, 0.75)])
        sample = mixed.get_frame(0.1)
        assert float(np.asarray(sample).mean()) == pytest.approx(0.4)
    finally:
        mixed.close()
        source.close()
        voiceover.close()


@pytest.mark.smoke
def test_video_source_audio_is_opt_in_and_mixes_with_voiceover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from moviepy import AudioClip, ColorClip, VideoFileClip

    source_path = tmp_path / "source.mp4"
    audio = AudioClip(lambda timestamp: 0.1 * np.sin(2 * np.pi * 440 * timestamp), duration=0.5, fps=44100)
    source = ColorClip((32, 32), color=(0, 128, 255), duration=0.5).with_audio(audio)
    try:
        source.write_videofile(str(source_path), fps=6, codec="libx264", audio_codec="aac", logger=None)
    finally:
        source.close()
        audio.close()

    muted_script = write_project(
        tmp_path, [{"type": "video", "src": "source.mp4", "duration": 0.5}]
    )
    muted_output = tmp_path / "muted.mp4"
    render_project(load_project(str(muted_script)), output_path=muted_output)
    muted = VideoFileClip(str(muted_output))
    try:
        assert muted.audio is None
    finally:
        muted.close()

    mixed_script = write_project(
        tmp_path,
        [
            {
                "type": "video",
                "src": "source.mp4",
                "duration": 0.5,
                "sourceAudioVolume": 0.5,
                "voiceover": "Mixed narration",
                "voiceoverVolume": 0.75,
            }
        ],
    )
    monkeypatch.setattr("clipscript.tts.TTSCache.synthesize", lambda self, text, request: source_path)
    mixed_output = tmp_path / "mixed.mp4"
    render_project(load_project(str(mixed_script)), output_path=mixed_output)
    mixed = VideoFileClip(str(mixed_output))
    try:
        assert mixed.audio is not None
        assert 0.4 <= mixed.duration <= 0.6
    finally:
        mixed.close()
