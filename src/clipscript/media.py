"""The only module that imports and adapts MoviePy 2.x APIs."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import Any

import numpy as np

try:
    from moviepy import (
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        VideoClip,
        VideoFileClip,
        concatenate_videoclips,
    )
    from moviepy.audio.fx import AudioFadeIn, AudioFadeOut, MultiplyVolume
    from moviepy.video.fx import CrossFadeIn
except ImportError as exc:  # pragma: no cover - exercised during installation failures.
    raise RuntimeError("MoviePy 2.x is required to render ClipScript projects") from exc


MediaClip = Any


class ClipTracker:
    """Closes all MoviePy clips, including intermediates, on success or failure."""

    def __init__(self) -> None:
        self._clips: list[MediaClip] = []
        self._ids: set[int] = set()

    def track(self, clip: MediaClip) -> MediaClip:
        if id(clip) not in self._ids:
            self._clips.append(clip)
            self._ids.add(id(clip))
        return clip

    def close_all(self) -> None:
        for clip in reversed(self._clips):
            # Closing must not hide a render exception or leak another resource.
            with suppress(Exception):
                clip.close()
        self._clips.clear()
        self._ids.clear()


def open_audio(path: Path) -> MediaClip:
    return AudioFileClip(str(path))


def open_video(path: Path) -> MediaClip:
    return VideoFileClip(str(path))


def make_frame_clip(frame_function: Any, duration: float) -> MediaClip:
    return VideoClip(frame_function=frame_function, duration=duration)


def make_image_clip(image: np.ndarray[Any, Any], duration: float) -> MediaClip:
    return ImageClip(image).with_duration(duration)


def subclip(clip: MediaClip, start: float, end: float) -> MediaClip:
    return clip.subclipped(start, end)


def crop(clip: MediaClip, coordinates: list[int]) -> MediaClip:
    x1, y1, x2, y2 = coordinates
    return clip.cropped(x1=x1, y1=y1, x2=x2, y2=y2)


def resize(clip: MediaClip, size: tuple[int, int]) -> MediaClip:
    return clip.resized(new_size=size)


def with_duration(clip: MediaClip, duration: float) -> MediaClip:
    return clip.with_duration(duration)


def with_position(clip: MediaClip, position: str) -> MediaClip:
    return clip.with_position(position)


def without_audio(clip: MediaClip) -> MediaClip:
    return clip.without_audio()


def with_audio(clip: MediaClip, audio: MediaClip) -> MediaClip:
    return clip.with_audio(audio)


def audio_of(clip: MediaClip) -> MediaClip | None:
    return clip.audio


def volume(clip: MediaClip, factor: float) -> MediaClip:
    return clip.with_effects([MultiplyVolume(factor)])


def mix_audio(clips: Iterable[MediaClip]) -> MediaClip:
    return CompositeAudioClip(list(clips))


def compose(clips: Iterable[MediaClip], size: tuple[int, int]) -> MediaClip:
    return CompositeVideoClip(list(clips), size=size)


def concatenate(clips: list[MediaClip], fades: list[float] | None = None) -> MediaClip:
    """Compose clips with fades entering each later clip and matching audio fades."""
    if not clips:
        raise ValueError("at least one clip is required")
    if not fades or not any(fades):
        return concatenate_videoclips(clips, method="compose")
    if len(fades) != len(clips):
        raise ValueError("transition list must match clip list")
    start = 0.0
    video_layers: list[MediaClip] = []
    audio_layers: list[MediaClip] = []
    for index, (clip, fade) in enumerate(zip(clips, fades)):
        visual = clip
        if index and fade:
            visual = visual.with_effects([CrossFadeIn(fade)])
        video_layers.append(visual.without_audio().with_start(start))
        if clip.audio is not None:
            audio = clip.audio
            if index and fade:
                audio = audio.with_effects([AudioFadeIn(fade)])
            if index + 1 < len(clips) and fades[index + 1]:
                audio = audio.with_effects([AudioFadeOut(fades[index + 1])])
            audio_layers.append(audio.with_start(start))
        start += duration(clip) - fade
    final = CompositeVideoClip(video_layers, size=size(clips[0])).with_duration(start)
    if audio_layers:
        final = final.with_audio(CompositeAudioClip(audio_layers))
    return final


def duration(clip: MediaClip) -> float:
    return float(clip.duration)


def size(clip: MediaClip) -> tuple[int, int]:
    return int(clip.w), int(clip.h)


def write_mp4(
    clip: MediaClip,
    output_path: Path,
    fps: int,
    temp_audio_path: Path,
) -> None:
    """Encode broadly compatible MP4 media with streamable metadata placement."""
    clip.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(temp_audio_path),
        remove_temp=True,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        logger=None,
    )
