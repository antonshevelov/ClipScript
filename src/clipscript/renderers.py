"""Scene renderers and their extensible registry."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, TypeVar, Union, cast

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont

from clipscript import media
from clipscript.models import ChatScene, OutroScene, Scene, TemplateConfig, TitleScene, VideoScene
from clipscript.project import resolve_path

Font = Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]
Frame = NDArray[np.uint8]
TScene = TypeVar("TScene", bound=Scene)


def get_system_font(font_name: str, size: int) -> Font:
    """Find a portable system font and use Pillow's built-in font as a last resort."""
    candidates: list[str] = []
    if font_name != "system" and os.path.exists(font_name):
        candidates.append(font_name)
    candidates.extend(
        [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_text(text: str, font: Font, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    lines: list[str] = []
    words = text.split()
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def draw_caption(image: Image.Image, text: str, font: Font) -> Image.Image:
    """Draw a responsive caption safe-area overlay on a PIL image."""
    width, height = image.size
    draw = ImageDraw.Draw(image, "RGBA")
    lines = wrap_text(text, font, max(1, int(width * 0.8)), draw)
    line_boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_heights = [box[3] - box[1] for box in line_boxes]
    text_width = max(box[2] - box[0] for box in line_boxes)
    padding_x, padding_y = max(8, width // 24), max(6, height // 60)
    gap = max(3, height // 240)
    rect_width = text_width + padding_x * 2
    rect_height = sum(line_heights) + gap * (len(lines) - 1) + padding_y * 2
    x1 = max(0, (width - rect_width) // 2)
    y1 = min(max(0, int(height * 0.75)), max(0, height - rect_height - padding_y))
    draw.rounded_rectangle(
        [x1, y1, x1 + rect_width, y1 + rect_height],
        radius=max(3, min(width, height) // 48),
        fill=(23, 33, 31, 200),
    )
    y = y1 + padding_y
    for line, box, line_height in zip(lines, line_boxes, line_heights):
        line_width = box[2] - box[0]
        draw.text((x1 + (rect_width - line_width) // 2, y), line, fill="#ffffff", font=font)
        y += line_height + gap
    return image


@dataclass(frozen=True)
class RenderContext:
    template: TemplateConfig
    script_dir: Path
    template_dir: Path
    font_regular: Font
    font_bold: Font
    caption_font: Font
    clips: media.ClipTracker


class SceneRenderer(Protocol):
    scene_type: str

    def render(self, scene: Scene, context: RenderContext, duration: float) -> media.MediaClip:
        """Render a scene visual clip."""


class RendererRegistry:
    """Maps scene type discriminators to renderer implementations."""

    def __init__(self) -> None:
        self._renderers: dict[str, SceneRenderer] = {}

    def register(self, renderer: SceneRenderer) -> None:
        if renderer.scene_type in self._renderers:
            raise ValueError(f"renderer already registered for '{renderer.scene_type}'")
        self._renderers[renderer.scene_type] = renderer

    def get(self, scene_type: str) -> SceneRenderer:
        try:
            return self._renderers[scene_type]
        except KeyError as exc:
            raise ValueError(f"no renderer registered for scene type '{scene_type}'") from exc


def draw_chat_frame(
    timestamp: float,
    scene: ChatScene,
    context: RenderContext,
    duration: float,
) -> Frame:
    width, height = context.template.resolution
    image = Image.new("RGBA", (width, height), context.template.surfaceColor)
    draw = ImageDraw.Draw(image, "RGBA")
    y_min = int(height * (0.15 if scene.chatHeader else 0.05))
    y_max = int(height * (0.73 if scene.chatHeader else 0.9))
    senders = (
        [
            ("Співрозмовник", "left", "#e5e5ea", "#17211f"),
            ("Ви", "right", context.template.brandColor, "#ffffff"),
        ]
        if scene.participantCount == 2
        else [
            ("Марія", "left", "#e5e5ea", "#17211f"),
            ("Ви", "right", context.template.brandColor, "#ffffff"),
            ("Олексій", "left", "#e5e5ea", "#17211f"),
        ]
    )
    messages = scene.messages or []
    start_time = min(0.2, duration / 4)
    end_time = max(start_time, duration - min(1.2, duration / 4))
    step = (end_time - start_time) / max(len(messages) - 1, 1)
    visible = [
        (message, senders[index % len(senders)])
        for index, message in enumerate(messages)
        if timestamp >= start_time + index * step
    ]
    bubble_max_width = max(40, int(width * 0.63))
    layouts: list[tuple[list[str], tuple[str, str, str, str], int, int, int]] = []
    total_height = 0
    for message, sender in visible:
        lines = wrap_text(message, context.font_regular, bubble_max_width, draw)
        boxes = [draw.textbbox((0, 0), line, font=context.font_regular) for line in lines]
        text_width = int(max(box[2] - box[0] for box in boxes))
        text_height = int(sum(box[3] - box[1] for box in boxes)) + max(2, height // 320) * (len(lines) - 1)
        bubble_width = int(text_width + max(20, width // 22))
        bubble_height = int(text_height + max(18, height // 25))
        name_height = max(14, height // 64) if scene.senderNames and sender[1] == "left" else 0
        entry_height = bubble_height + name_height + max(8, height // 90)
        layouts.append((lines, sender, bubble_width, bubble_height, name_height))
        total_height += entry_height
    y = y_max - total_height if total_height > y_max - y_min else y_min
    margin = max(12, width // 18)
    for lines, sender, bubble_width, bubble_height, name_height in layouts:
        name, side, color, text_color = sender
        x = margin if side == "left" else width - margin - bubble_width
        if name_height:
            draw.text((x + max(4, width // 120), y), name, fill="#8e8e93", font=context.font_regular)
            y += name_height
        draw.rounded_rectangle(
            [x, y, x + bubble_width, y + bubble_height],
            radius=max(8, width // 45),
            fill=color,
        )
        line_y = y + max(8, height // 95)
        for line in lines:
            draw.text((x + max(10, width // 45), line_y), line, fill=text_color, font=context.font_regular)
            box = draw.textbbox((0, 0), line, font=context.font_regular)
            line_y += int(box[3] - box[1]) + max(2, height // 320)
        y += bubble_height + max(8, height // 90)
    if scene.chatHeader:
        header_height = max(30, int(height * 0.125))
        draw.rectangle([0, 0, width, header_height], fill=context.template.surfaceColor)
        draw.line([(0, header_height), (width, header_height)], fill="#e0dcd3", width=max(1, width // 540))
        for text, font, y_offset, color in (
            (scene.chatTitle, context.font_bold, int(header_height * 0.25), context.template.textColor),
            (scene.chatSubtitle, context.font_regular, int(header_height * 0.58), "#8e8e93"),
        ):
            box = draw.textbbox((0, 0), text, font=font)
            draw.text(((width - (box[2] - box[0])) // 2, y_offset), text, fill=color, font=font)
    if scene.caption:
        image = draw_caption(image, scene.caption, context.caption_font)
    return np.asarray(image.convert("RGB"))


def make_static_slide(scene: TitleScene | OutroScene, context: RenderContext) -> Image.Image:
    width, height = context.template.resolution
    background = context.template.surfaceColor if scene.type == "title" else context.template.brandColor
    image = Image.new("RGBA", (width, height), background)
    draw = ImageDraw.Draw(image, "RGBA")
    foreground = context.template.brandColor if scene.type == "title" else "#ffffff"
    lines = wrap_text(scene.caption or "", context.font_bold, max(1, int(width * 0.82)), draw)
    line_boxes = [draw.textbbox((0, 0), line, font=context.font_bold) for line in lines]
    line_height = max(box[3] - box[1] for box in line_boxes)
    total_height = line_height * len(lines) + max(3, height // 128) * (len(lines) - 1)
    y = max(0, (height - total_height) // 2)
    if isinstance(scene, OutroScene) and context.template.logo:
        logo_path = resolve_path(context.template.logo, base_dir=context.template_dir)
        if logo_path.is_file():
            with Image.open(logo_path) as logo:
                logo_size = min(max(24, width // 4), max(24, height // 4))
                resized_logo = logo.convert("RGBA").resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                image.paste(
                    resized_logo,
                    ((width - logo_size) // 2, int(max(0, y - logo_size - 20))),
                    resized_logo,
                )
    for line, box in zip(lines, line_boxes):
        line_width = box[2] - box[0]
        draw.text(((width - line_width) // 2, y), line, fill=foreground, font=context.font_bold)
        y += line_height + max(3, height // 128)
    if isinstance(scene, OutroScene) and scene.url:
        box = draw.textbbox((0, 0), scene.url, font=context.font_regular)
        draw.text(((width - (box[2] - box[0])) // 2, min(height - 20, y + height // 24)), scene.url, fill="#ffffff", font=context.font_regular)
    return image


class ChatRenderer:
    scene_type = "chat"

    def render(self, scene: Scene, context: RenderContext, duration: float) -> media.MediaClip:
        chat_scene = cast(ChatScene, scene)

        def frame_function(timestamp: float) -> Frame:
            return draw_chat_frame(timestamp, chat_scene, context, duration)

        return context.clips.track(media.make_frame_clip(frame_function, duration))


class StaticRenderer:
    def __init__(self, scene_type: Literal["title", "outro"]) -> None:
        self.scene_type: str = scene_type

    def render(self, scene: Scene, context: RenderContext, duration: float) -> media.MediaClip:
        static_scene = cast(Union[TitleScene, OutroScene], scene)
        image = make_static_slide(static_scene, context)
        return context.clips.track(media.make_image_clip(np.asarray(image), duration))


class VideoRenderer:
    scene_type = "video"

    def render(self, scene: Scene, context: RenderContext, duration: float) -> media.MediaClip:
        video_scene = cast(VideoScene, scene)
        source_path = resolve_path(video_scene.src, base_dir=context.script_dir)
        if not source_path.is_file():
            raise ValueError(f"video file '{video_scene.src}' was not found")
        source = context.clips.track(media.open_video(source_path))
        source_duration = media.duration(source)
        start = min(video_scene.start, source_duration)
        requested_end = video_scene.end
        if requested_end is None:
            requested_end = video_scene.start + (video_scene.duration or duration)
        end = min(requested_end, source_duration)
        if end <= start:
            raise ValueError("video trim is outside the source clip duration")
        sliced = context.clips.track(media.subclip(source, start, end))
        actual_duration = media.duration(sliced)
        if video_scene.crop:
            sliced = context.clips.track(media.crop(sliced, video_scene.crop))
        target_width, target_height = context.template.resolution
        source_width, source_height = media.size(sliced)
        scale = min(target_width / source_width, target_height / source_height)
        resized = context.clips.track(
            media.resize(sliced, (max(1, int(source_width * scale)), max(1, int(source_height * scale))))
        )
        background = np.asarray(
            Image.new("RGB", (target_width, target_height), video_scene.backgroundColor or context.template.surfaceColor)
        )
        background_clip = context.clips.track(media.make_image_clip(background, actual_duration))
        centered = context.clips.track(media.with_position(resized, "center"))
        layers = [background_clip, centered]
        if video_scene.caption:
            caption = draw_caption(
                Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0)),
                video_scene.caption,
                context.caption_font,
            )
            layers.append(context.clips.track(media.make_image_clip(np.asarray(caption), actual_duration)))
        composite = context.clips.track(media.compose(layers, (target_width, target_height)))
        return context.clips.track(media.without_audio(composite))


def default_renderer_registry() -> RendererRegistry:
    registry = RendererRegistry()
    registry.register(ChatRenderer())
    registry.register(StaticRenderer("title"))
    registry.register(VideoRenderer())
    registry.register(StaticRenderer("outro"))
    return registry
