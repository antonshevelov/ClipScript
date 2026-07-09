"""Subtitle planning and a small deterministic UTF-8 SRT writer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clipscript.models import Scene


@dataclass(frozen=True)
class SubtitleCue:
    start: float
    end: float
    text: str


def subtitle_text(scene: Scene) -> str | None:
    return scene.subtitle or scene.voiceover


def plan_subtitles(scenes: list[Scene], durations: list[float], fades: list[float]) -> list[SubtitleCue]:
    """Place scene cues on the final timeline, including fade overlaps."""
    cues: list[SubtitleCue] = []
    start = 0.0
    for index, (scene, duration) in enumerate(zip(scenes, durations)):
        text = subtitle_text(scene)
        if text:
            cues.append(SubtitleCue(start=start, end=start + duration, text=text))
        next_fade = fades[index + 1] if index + 1 < len(fades) else 0.0
        start += duration - next_fade
    return cues


def _timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}"


def write_srt(cues: list[SubtitleCue], output_path: Path) -> Path:
    lines: list[str] = []
    for index, cue in enumerate(cues, start=1):
        lines.extend([str(index), f"{_timestamp(cue.start)} --> {_timestamp(cue.end)}", cue.text, ""])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
