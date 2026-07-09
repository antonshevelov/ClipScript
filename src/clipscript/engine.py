"""Render orchestration independent from CLI presentation concerns."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

from clipscript import media
from clipscript.models import ChatScene, OutroScene, Scene, TitleScene, VideoScene
from clipscript.project import Project, resolve_path
from clipscript.renderers import (
    RenderContext,
    RendererRegistry,
    default_renderer_registry,
    get_system_font,
)
from clipscript.tts import TTSCache, TTSRegistry, default_tts_registry, request_from_template

ProgressCallback = Callable[[str], None]


def validate_project_references(project: Project) -> None:
    """Validate paths whose existence cannot be checked by the JSON schema alone."""
    for scene in project.script.scenes:
        if scene.type == "video":
            source_path = resolve_path(scene.src, base_dir=project.script_dir)
            if not source_path.is_file():
                raise ValueError(f"video file '{scene.src}' was not found")
    if project.template.logo:
        logo_path = resolve_path(project.template.logo, base_dir=project.template_dir)
        if not logo_path.is_file():
            raise ValueError(f"template logo '{project.template.logo}' was not found")


def scene_duration(scene: Scene, audio_duration: float) -> float:
    """Select timing while preserving the unversioned 0.1.0 fallback behavior."""
    if isinstance(scene, (ChatScene, TitleScene, OutroScene)):
        requested = scene.duration or 0.0
        return max(requested, audio_duration) or 5.0
    if isinstance(scene, VideoScene):
        return scene.duration or audio_duration or 5.0
    raise ValueError(f"unsupported scene type '{scene.type}'")


def render_project(
    project: Project,
    output_path: Path | None = None,
    cache_dir: Path | None = None,
    renderers: RendererRegistry | None = None,
    providers: TTSRegistry | None = None,
    progress: ProgressCallback | None = None,
) -> Path:
    """Render a project and close every MoviePy resource even when rendering fails."""
    validate_project_references(project)
    output = output_path or resolve_path(project.script.output, base_dir=project.script_dir)
    if output.suffix.lower() != ".mp4":
        raise ValueError("output file must use the .mp4 extension")
    output.parent.mkdir(parents=True, exist_ok=True)

    effective_cache_dir = cache_dir or Path(
        os.environ.get("CLIPSCRIPT_CACHE_DIR", Path.cwd() / ".clipscript" / "cache" / "tts")
    )
    tts_cache = TTSCache(effective_cache_dir, providers or default_tts_registry())
    registry = renderers or default_renderer_registry()
    tracker = media.ClipTracker()
    context = RenderContext(
        template=project.template,
        script_dir=project.script_dir,
        template_dir=project.template_dir,
        font_regular=get_system_font(project.template.fontFamily, 36),
        font_bold=get_system_font(project.template.fontFamily, 48),
        caption_font=get_system_font(project.template.fontFamily, 38),
        clips=tracker,
    )
    temp_audio_path = output.parent / f".{output.stem}.{uuid.uuid4().hex}.m4a"
    clips: list[media.MediaClip] = []
    tts_request = request_from_template(project.template)
    try:
        for index, scene in enumerate(project.script.scenes, start=1):
            if progress:
                progress(f"Rendering scene {index}/{len(project.script.scenes)} ({scene.type})")
            audio_duration = 0.0
            audio_clip: media.MediaClip | None = None
            if scene.voiceover is not None:
                if progress:
                    progress(f"Generating voiceover for scene {index}")
                audio_path = tts_cache.synthesize(scene.voiceover, tts_request)
                audio_clip = tracker.track(media.open_audio(audio_path))
                audio_duration = media.duration(audio_clip)

            visual = registry.get(scene.type).render(scene, context, scene_duration(scene, audio_duration))
            visual_duration = media.duration(visual)
            if audio_clip is not None:
                audio_for_scene = audio_clip
                if audio_duration > visual_duration:
                    audio_for_scene = tracker.track(media.with_duration(audio_clip, visual_duration))
                visual = tracker.track(media.with_audio(visual, audio_for_scene))
            clips.append(visual)

        if progress:
            progress("Concatenating scenes")
        final_clip = tracker.track(media.concatenate(clips))
        if progress:
            progress("Writing MP4")
        media.write_mp4(final_clip, output, project.template.fps, temp_audio_path)
    finally:
        temp_audio_path.unlink(missing_ok=True)
        tracker.close_all()
    return output
