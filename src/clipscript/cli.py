#!/usr/bin/env python3
"""
ClipScript
Script-driven vertical video generator for social promos, tutorials, and product demos.
"""

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Monkey patch for older moviepy version compatibility with PIL 10+
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from typing import Optional

import typer
from pydantic import BaseModel, validator
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

# MoviePy imports
try:
    from moviepy.editor import (
        AudioFileClip,
        CompositeVideoClip,
        ImageClip,
        VideoFileClip,
        concatenate_videoclips,
    )
    from moviepy.video.VideoClip import VideoClip
except ImportError:
    print("Error: moviepy is not installed. Install dependencies first.")
    sys.exit(1)

# edge-tts imports
try:
    import edge_tts
except ImportError:
    print("Error: edge-tts is not installed. Install dependencies first.")
    sys.exit(1)

app = typer.Typer(help="Generate vertical videos from JSON scripts.")
console = Console()

# Get the directory where this package module is located.
PACKAGE_DIR = Path(__file__).parent.resolve()


def resolve_path(path: str, base_dir: Optional[Path] = None) -> Path:
    """Resolve a path using a predictable set of bases.

    Resolution order:
    - absolute paths are returned as-is;
    - paths relative to `base_dir` when provided;
    - paths relative to the current working directory;
    - paths relative to the package directory.

    This keeps JSON scenarios portable: paths inside a script can be relative to
    that script file, while CLI paths still work from the shell.
    """
    p = Path(path)

    if p.is_absolute():
        return p

    candidates = []
    if base_dir is not None:
        candidates.append(base_dir / p)
    candidates.extend([Path.cwd() / p, PACKAGE_DIR / p])

    for candidate in candidates:
        if candidate.exists() or candidate.parent.exists():
            return candidate

    return candidates[0]

VALID_SCENE_TYPES = {"chat", "title", "video", "outro"}

class Scene(BaseModel):
    type: str  # chat, title, video, outro
    duration: Optional[float] = None
    caption: Optional[str] = None
    messages: Optional[list[str]] = None
    chatHeader: Optional[bool] = True
    chatTitle: Optional[str] = "Shared list"
    chatSubtitle: Optional[str] = "Two participants"
    senderNames: Optional[bool] = True
    participantCount: Optional[int] = 3
    src: Optional[str] = None
    crop: Optional[list[int]] = None
    backgroundColor: Optional[str] = None
    start: Optional[float] = 0.0
    end: Optional[float] = None
    url: Optional[str] = None
    
    @validator('type')
    def validate_type(cls, v):
        if v not in VALID_SCENE_TYPES:
            raise ValueError(f"Invalid scene type: {v}. Must be one of {VALID_SCENE_TYPES}")
        return v
    
    @validator('end')
    def validate_end_greater_than_start(cls, v, values):
        if v is not None and values.get('start') is not None and v <= values['start']:
            raise ValueError("end must be greater than start")
        return v

    @validator('crop')
    def validate_crop(cls, v):
        if v is not None and (len(v) != 4 or v[2] <= v[0] or v[3] <= v[1]):
            raise ValueError("crop must be [x1, y1, x2, y2] with x2 > x1 and y2 > y1")
        return v

class TemplateConfig(BaseModel):
    resolution: list[int] = [1080, 1920]
    fps: int = 30
    brandColor: str = "#0f7b6c"
    surfaceColor: str = "#fdf9f1"
    textColor: str = "#17211f"
    accentColor: str = "#43a047"
    logo: Optional[str] = None
    voice: str = "uk-UA-PolinaNeural"
    voice_id: Optional[str] = None  # For ElevenLabs
    elevenlabsModelId: str = "eleven_multilingual_v2"
    fontFamily: str = "system"
    ttsProvider: str = "edge"  # "edge" or "elevenlabs"
    
    @validator('ttsProvider')
    def validate_tts_provider(cls, v):
        valid_providers = {"edge", "elevenlabs"}
        if v not in valid_providers:
            raise ValueError(f"Invalid TTS provider: {v}. Must be one of {valid_providers}")
        return v
    
    @validator('resolution')
    def validate_resolution(cls, v):
        if len(v) != 2 or v[0] <= 0 or v[1] <= 0:
            raise ValueError("resolution must be [width, height] with positive values")
        return v

class VideoConfig(BaseModel):
    title: str
    output: str
    template: str
    voiceover: list[str]
    scenes: list[Scene]
    
    @validator('scenes')
    def validate_voiceover_count(cls, v, values):
        if values.get('voiceover') is not None:
            if len(values['voiceover']) != len(v):
                raise ValueError(f"Number of voiceover entries ({len(values['voiceover'])}) must match number of scenes ({len(v)})")
        return v

# ==========================================
# FONT HELPER
# ==========================================

def get_system_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    """Finds and loads standard fonts on macOS or falls back gracefully."""
    paths = []
    if font_name and font_name != "system" and os.path.exists(font_name):
        paths.append(font_name)

    # Standard macOS font paths
    mac_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial.ttf"
    ]
    paths.extend(mac_paths)

    # Standard Linux font paths
    linux_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    ]
    paths.extend(linux_paths)

    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    
    # Absolute fallback
    return ImageFont.load_default()

# ==========================================
# TEXT WRAPPING
# ==========================================

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Wraps text to fit within a given pixel width."""
    words = text.split(' ')
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        # Measure text line width
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            
    if current_line:
        lines.append(' '.join(current_line))
        
    return lines

# ==========================================
# CAPTION DRAWING HELPER
# ==========================================

def draw_caption_on_image(img: Image.Image, text: str, font: ImageFont.FreeTypeFont, template: TemplateConfig) -> Image.Image:
    """Draws a burned-in caption with a transparent dark backing rectangle near the bottom."""
    if not text:
        return img
        
    # Standard width/height
    w, h = img.size
    draw = ImageDraw.Draw(img, "RGBA")
    
    # Wrap text to max 850px width
    wrapped_lines = wrap_text(text, font, 850, draw)
    
    # Calculate line heights and total width/height
    line_heights = []
    max_line_w = 0
    for line in wrapped_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        max_line_w = max(max_line_w, line_w)
        line_heights.append(line_h)
        
    text_w = max_line_w
    text_h = sum(line_heights) + (len(wrapped_lines) - 1) * 8
    
    # Padding around text
    pad_x = 40
    pad_y = 25
    rect_w = text_w + pad_x * 2
    rect_h = text_h + pad_y * 2
    
    # Centered horizontally, safe area Y at 1450
    rect_x1 = (w - rect_w) // 2
    rect_y1 = 1450
    rect_x2 = rect_x1 + rect_w
    rect_y2 = rect_y1 + rect_h
    
    # Draw dark backing bar
    draw.rounded_rectangle([rect_x1, rect_y1, rect_x2, rect_y2], radius=20, fill=(23, 33, 31, 200))
    
    # Draw text lines
    curr_y = rect_y1 + pad_y
    for line in wrapped_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        lx = rect_x1 + (rect_w - lw) // 2
        draw.text((lx, curr_y), line, fill="#ffffff", font=font)
        curr_y += (bbox[3] - bbox[1]) + 8
        
    return img

# ==========================================
# CHAT SCENE RENDERER
# ==========================================

def draw_chat_frame(
    t: float,
    duration: float,
    messages: list[str],
    template: TemplateConfig,
    font_regular: ImageFont.FreeTypeFont,
    font_bold: ImageFont.FreeTypeFont,
    show_header: bool = True,
    chat_title: str = "Shared list",
    chat_subtitle: str = "Two participants",
    show_sender_names: bool = True,
    participant_count: int = 3,
) -> np.ndarray:
    """Generates a single frame of the chat simulation scene at time t."""
    width, height = template.resolution
    img = Image.new("RGBA", (width, height), template.surfaceColor)
    draw = ImageDraw.Draw(img, "RGBA")
    
    # Y viewport for chat messages
    y_min = 280 if show_header else 90
    y_max = 1400 if show_header else height - 120
    viewport_height = y_max - y_min
    
    # Define senders to alternate
    if participant_count == 2:
        senders = [
            {"name": "Співрозмовник", "side": "left", "color": "#e5e5ea", "text_color": "#17211f"},
            {"name": "Ви", "side": "right", "color": template.brandColor, "text_color": "#ffffff"},
        ]
    else:
        senders = [
            {"name": "Марія", "side": "left", "color": "#e5e5ea", "text_color": "#17211f"},
            {"name": "Ви", "side": "right", "color": template.brandColor, "text_color": "#ffffff"},
            {"name": "Олексій", "side": "left", "color": "#e5e5ea", "text_color": "#17211f"},
        ]
    
    n_msg = len(messages)
    start_t = 0.2
    end_t = duration - 1.2
    step = (end_t - start_t) / max(n_msg - 1, 1)
    
    visible_messages = []
    for i, msg in enumerate(messages):
        msg_t = start_t + i * step
        if t >= msg_t:
            sender = senders[i % len(senders)]
            visible_messages.append((msg, sender))
            
    # Measure heights of visible bubbles
    max_bubble_w = 680
    msg_layouts = []
    total_height = 0
    
    for msg_text, sender in visible_messages:
        wrapped = wrap_text(msg_text, font_regular, max_bubble_w, draw)
        line_heights = []
        max_line_w = 0
        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=font_regular)
            line_w = bbox[2] - bbox[0]
            line_h = bbox[3] - bbox[1]
            max_line_w = max(max_line_w, line_w)
            line_heights.append(line_h)
            
        text_w = max_line_w
        text_h = sum(line_heights) + (len(wrapped) - 1) * 6
        
        bubble_w = text_w + 50
        bubble_h = text_h + 40
        
        name_h = 30 if show_sender_names and sender["side"] == "left" else 0
        total_h = bubble_h + name_h + 15
        
        msg_layouts.append({
            "text_lines": wrapped,
            "sender": sender,
            "bubble_w": bubble_w,
            "bubble_h": bubble_h,
            "total_h": total_h,
            "name_h": name_h
        })
        total_height += total_h
        
    # Vertical scroll offset
    y_cursor = y_min
    if total_height > viewport_height:
        y_cursor = y_max - total_height
        
    for layout in msg_layouts:
        sender = layout["sender"]
        bubble_w = layout["bubble_w"]
        bubble_h = layout["bubble_h"]
        
        if sender["side"] == "left":
            x_bubble = 60
            if show_sender_names:
                draw.text((x_bubble + 10, y_cursor), sender["name"], fill="#8E8E93", font=font_regular)
                y_cursor += layout["name_h"]
            
            # Bubble bg
            bubble_xy = [x_bubble, y_cursor, x_bubble + bubble_w, y_cursor + bubble_h]
            draw.rounded_rectangle(bubble_xy, radius=24, fill=sender["color"])
            
            # Text lines
            curr_y = y_cursor + 20
            for line in layout["text_lines"]:
                draw.text((x_bubble + 25, curr_y), line, fill=sender["text_color"], font=font_regular)
                bbox = draw.textbbox((0, 0), line, font=font_regular)
                curr_y += (bbox[3] - bbox[1]) + 6
        else:
            x_bubble = width - 60 - bubble_w
            # Bubble bg
            bubble_xy = [x_bubble, y_cursor, x_bubble + bubble_w, y_cursor + bubble_h]
            draw.rounded_rectangle(bubble_xy, radius=24, fill=sender["color"])
            
            # Text lines
            curr_y = y_cursor + 20
            for line in layout["text_lines"]:
                draw.text((x_bubble + 25, curr_y), line, fill=sender["text_color"], font=font_regular)
                bbox = draw.textbbox((0, 0), line, font=font_regular)
                curr_y += (bbox[3] - bbox[1]) + 6
                
        y_cursor += bubble_h + 15
        
    if show_header:
        header_h = 240
        draw.rectangle([0, 0, width, header_h], fill=template.surfaceColor)
        draw.line([(0, header_h), (width, header_h)], fill="#e0dcd3", width=2)
        
        title_str = chat_title
        bbox_title = draw.textbbox((0, 0), title_str, font=font_bold)
        tw = bbox_title[2] - bbox_title[0]
        draw.text(((width - tw) // 2, 70), title_str, fill=template.textColor, font=font_bold)
        
        sub_str = chat_subtitle
        bbox_sub = draw.textbbox((0, 0), sub_str, font=font_regular)
        sw = bbox_sub[2] - bbox_sub[0]
        draw.text(((width - sw) // 2, 130), sub_str, fill="#8E8E93", font=font_regular)
    
    return np.array(img.convert("RGB"))

# ==========================================
# STATIC SLIDE GENERATOR
# ==========================================

def generate_static_slide(
    scene_type: str,
    caption: str,
    template: TemplateConfig,
    font_regular: ImageFont.FreeTypeFont,
    font_bold: ImageFont.FreeTypeFont,
    url: str = None,
    asset_base_dir: Optional[Path] = None,
) -> Image.Image:
    """Generates a static slide for TITLE or OUTRO scenes."""
    width, height = template.resolution
    
    if scene_type == "title":
        img = Image.new("RGBA", (width, height), template.surfaceColor)
        draw = ImageDraw.Draw(img, "RGBA")
        
        # Centered caption
        if caption:
            wrapped = wrap_text(caption, font_bold, 900, draw)
            line_heights = []
            max_line_w = 0
            for line in wrapped:
                bbox = draw.textbbox((0, 0), line, font=font_bold)
                max_line_w = max(max_line_w, bbox[2] - bbox[0])
                line_heights.append(bbox[3] - bbox[1])
                
            total_h = sum(line_heights) + (len(wrapped) - 1) * 15
            curr_y = (height - total_h) // 2
            
            for line in wrapped:
                bbox = draw.textbbox((0, 0), line, font=font_bold)
                lw = bbox[2] - bbox[0]
                draw.text(((width - lw) // 2, curr_y), line, fill=template.brandColor, font=font_bold)
                curr_y += (bbox[3] - bbox[1]) + 15
                
    elif scene_type == "outro":
        img = Image.new("RGBA", (width, height), template.brandColor)
        draw = ImageDraw.Draw(img, "RGBA")
        
        # Load and paste logo
        logo_y = 550
        logo_path = resolve_path(template.logo, base_dir=asset_base_dir) if template.logo else None
        if logo_path and logo_path.exists():
            try:
                logo_img = Image.open(str(logo_path)).convert("RGBA")
                logo_img = logo_img.resize((240, 240), Image.Resampling.LANCZOS)
                # Paste logo
                logo_x = (width - 240) // 2
                img.paste(logo_img, (logo_x, logo_y), logo_img)
                logo_y += 280
            except Exception as e:
                console.print(f"[yellow]Warning: could not load logo: {e}[/yellow]")
        
        # Draw Outro caption
        text_y = logo_y
        if caption:
            wrapped = wrap_text(caption, font_bold, 900, draw)
            for line in wrapped:
                bbox = draw.textbbox((0, 0), line, font=font_bold)
                lw = bbox[2] - bbox[0]
                draw.text(((width - lw) // 2, text_y), line, fill="#ffffff", font=font_bold)
                text_y += (bbox[3] - bbox[1]) + 15
                
        if url:
            url_y = text_y + 40
            bbox_url = draw.textbbox((0, 0), url, font=font_regular)
            uw = bbox_url[2] - bbox_url[0]
            draw.text(((width - uw) // 2, url_y), url, fill="#ffffff", font=font_regular)
        
    else:
        # Default placeholder slide
        img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
        
    return img

# ==========================================
# TTS PROVIDERS
# ==========================================

async def amain_tts_edge(text: str, voice: str, output_file: str) -> None:
    """Async wrapper for edge-tts."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)


def generate_tts_edge(text: str, voice: str, output_file: str) -> None:
    """Generate TTS using Microsoft Edge TTS."""
    asyncio.run(amain_tts_edge(text, voice, output_file))


def generate_tts_elevenlabs(
    text: str,
    voice_id: str,
    model_id: str,
    output_file: str,
    api_key: str,
) -> None:
    """Generate TTS using ElevenLabs API."""
    import requests
    
    # ElevenLabs TTS API endpoint
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mp3",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }
    
    response = requests.post(url, json=data, headers=headers, timeout=60)
    
    if response.status_code != 200:
        raise Exception(f"ElevenLabs API error: {response.status_code} - {response.text}")
    
    # Save the audio
    with open(output_file, "wb") as f:
        f.write(response.content)


def generate_tts_cached(
    text: str,
    provider: str,
    voice: str,
    voice_id: Optional[str],
    elevenlabs_model_id: str,
    cache_dir: str,
) -> str:
    """Generates audio for text using the specified TTS provider and caches it.
    
    Cache key includes: text, provider, voice/voice_id/model to prevent conflicts between providers.
    """
    os.makedirs(cache_dir, exist_ok=True)
    
    # For elevenlabs, use voice_id from template or ELEVENLABS_VOICE_ID env var
    effective_voice_id = voice_id
    if provider == "elevenlabs" and not effective_voice_id:
        effective_voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
        if not effective_voice_id:
            raise ValueError(
                "voice_id is required for elevenlabs provider. "
                "Please set it in the template or ELEVENLABS_VOICE_ID environment variable."
            )
    
    # Create cache key based on provider
    if provider == "edge":
        cache_key = f"{text}||edge||{voice}"
    elif provider == "elevenlabs":
        cache_key = f"{text}||elevenlabs||{effective_voice_id}||{elevenlabs_model_id}"
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")
    
    h = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
    cache_path = os.path.join(cache_dir, f"{h}.mp3")
    
    if os.path.exists(cache_path):
        return cache_path
    
    # Generate based on provider
    if provider == "edge":
        generate_tts_edge(text, voice, cache_path)
    elif provider == "elevenlabs":
        # Get environment variables
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY environment variable is required for elevenlabs provider. "
                "Please set it and try again."
            )
        generate_tts_elevenlabs(text, effective_voice_id, elevenlabs_model_id, cache_path, api_key)
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")
    
    return cache_path

# ==========================================
# MAIN GENERATION PROCESS
# ==========================================

@app.command()
def generate(
    input_path: str = typer.Option("examples/scripts/chat-only.json", "--input", "-i", help="Path to a JSON video script."),
    output_path: Optional[str] = typer.Option(None, "--output", "-o", help="Path for the final MP4."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite the output file if it already exists.")
):
    """Generate a vertical video from a JSON script."""
    console.print("[bold green]=== ClipScript ===[/bold green]")
    
    # 1. Validation checks
    input_file = resolve_path(input_path)
    if not input_file.exists():
        console.print(f"[red]Error: script file '{input_path}' was not found.[/red]")
        raise typer.Exit(1)
    script_base_dir = input_file.parent
        
    try:
        with open(str(input_file), encoding="utf-8") as f:
            script_data = json.load(f)
        config = VideoConfig(**script_data)
    except Exception as e:
        console.print(f"[red]Script validation error: {e}[/red]")
        raise typer.Exit(1) from e
        
    template_file = resolve_path(config.template, base_dir=script_base_dir)
    if not template_file.exists():
        console.print(f"[red]Error: template file '{config.template}' was not found.[/red]")
        raise typer.Exit(1)
    template_base_dir = template_file.parent
        
    try:
        with open(str(template_file), encoding="utf-8") as f:
            template_data = json.load(f)
        template = TemplateConfig(**template_data)
    except Exception as e:
        console.print(f"[red]Template validation error: {e}[/red]")
        raise typer.Exit(1) from e
        
    # Resolve final output path
    final_output = output_path or config.output
    output_file = resolve_path(final_output, base_dir=script_base_dir)
    
    if not str(output_file).endswith(".mp4"):
        console.print("[red]Error: output file must have a .mp4 extension.[/red]")
        raise typer.Exit(1)
        
    if output_file.exists() and not overwrite:
        console.print(f"[yellow]Output '{final_output}' already exists. Use --overwrite to replace it.[/yellow]")
        raise typer.Exit(0)
        
    # Make output dir
    os.makedirs(str(output_file.parent), exist_ok=True)
    
    # Load fonts
    font_family = template.fontFamily
    font_regular = get_system_font(font_family, 36)
    font_bold = get_system_font(font_family, 48)
    caption_font = get_system_font(font_family, 38)
    
    # 2. TTS Voiceover Generation
    cache_dir = os.environ.get("CLIPSCRIPT_CACHE_DIR") or str(Path.cwd() / ".clipscript" / "cache" / "tts")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        # Voiceover TTS Generation
        tts_task = progress.add_task("[cyan]Generating voiceover (TTS)...", total=len(config.voiceover))
        tts_files = []
        for i, text in enumerate(config.voiceover):
            try:
                progress.update(tts_task, description=f"[cyan]Voiceover scene {i+1}: {text[:30]}...")
                f_path = generate_tts_cached(
                    text, 
                    template.ttsProvider, 
                    template.voice, 
                    template.voice_id,
                    template.elevenlabsModelId,
                    cache_dir
                )
                tts_files.append(f_path)
                progress.advance(tts_task)
            except Exception as e:
                console.print(f"[red]Voiceover generation failed for '{text}': {e}[/red]")
                raise typer.Exit(1) from e
                
        # 3. Scenes Generation
        scene_task = progress.add_task("[green]Building scene clips...", total=len(config.scenes))
        clips = []
        
        for i, scene in enumerate(config.scenes):
            progress.update(scene_task, description=f"[green]Rendering scene {i+1} ({scene.type})...")
            
            # Load corresponding voiceover
            voice_file = tts_files[i] if i < len(tts_files) else None
            audio_clip = AudioFileClip(voice_file) if voice_file else None
            
            # Target duration (sync with audio duration)
            audio_duration = audio_clip.duration if audio_clip else 0.0
            specified_duration = scene.duration or 0.0
            
            # For static/chat scenes, stretch duration to voiceover
            if scene.type in ["chat", "title", "outro"]:
                scene_duration = max(specified_duration, audio_duration)
                if scene_duration <= 0.0:
                    scene_duration = 5.0 # fallback
            else:
                # For video scene, use explicit clip duration
                if scene.end is not None:
                    scene_duration = scene.end - scene.start
                elif specified_duration > 0.0:
                    scene_duration = specified_duration
                else:
                    scene_duration = audio_duration or 5.0
            
            # Render visual part based on scene type
            if scene.type == "chat":
                msg_list = scene.messages or []
                show_header = scene.chatHeader is not False
                chat_title = scene.chatTitle or "Shared list"
                chat_subtitle = scene.chatSubtitle or "Two participants"
                show_sender_names = scene.senderNames is not False
                participant_count = scene.participantCount or 3
                chat_duration = scene_duration
                chat_caption = scene.caption
                
                # Make dynamic frame generator
                def make_frame(
                    t,
                    duration=chat_duration,
                    messages=msg_list,
                    caption=chat_caption,
                    header=show_header,
                    title=chat_title,
                    subtitle=chat_subtitle,
                    sender_names=show_sender_names,
                    participants=participant_count,
                ):
                    frm = draw_chat_frame(
                        t,
                        duration,
                        messages,
                        template,
                        font_regular,
                        font_bold,
                        show_header=header,
                        chat_title=title,
                        chat_subtitle=subtitle,
                        show_sender_names=sender_names,
                        participant_count=participants,
                    )
                    # Burn in caption if any
                    if caption:
                        pil_frm = Image.fromarray(frm)
                        pil_frm = draw_caption_on_image(pil_frm, caption, caption_font, template)
                        frm = np.array(pil_frm)
                    return frm
                    
                clip = VideoClip(make_frame, duration=scene_duration)
                
            elif scene.type in ["title", "outro"]:
                # Draw static image - pass url for outro scenes
                url = scene.url if scene.type == "outro" and scene.url else None
                slide_img = generate_static_slide(
                    scene.type,
                    scene.caption,
                    template,
                    font_regular,
                    font_bold,
                    url,
                    asset_base_dir=template_base_dir,
                )
                # For outro, caption is already drawn on the slide, but for title we can draw it as well
                slide_np = np.array(slide_img.convert("RGB"))
                clip = ImageClip(slide_np).set_duration(scene_duration)
                
            elif scene.type == "video":
                # Check video file
                if not scene.src:
                    console.print("[red]Error: video scenes require a src field.[/red]")
                    raise typer.Exit(1)
                video_src = resolve_path(scene.src, base_dir=script_base_dir)
                # Check if video file exists
                if not video_src.exists():
                    console.print(f"[red]Error: video file '{scene.src}' was not found.[/red]")
                    raise typer.Exit(1)
                    
                # Load video
                full_vid = VideoFileClip(str(video_src))
                
                # Slice
                start_limit = min(scene.start, full_vid.duration)
                end_limit = min(scene.end or full_vid.duration, full_vid.duration)
                sliced_vid = full_vid.subclip(start_limit, end_limit)

                if scene.crop:
                    x1, y1, x2, y2 = scene.crop
                    sliced_vid = sliced_vid.crop(x1=x1, y1=y1, x2=x2, y2=y2)
                
                # Resize and pad (contain inside resolution)
                tgt_w, tgt_h = template.resolution
                scale = min(tgt_w / sliced_vid.w, tgt_h / sliced_vid.h)
                new_w = int(sliced_vid.w * scale)
                new_h = int(sliced_vid.h * scale)
                
                resized_vid = sliced_vid.resize(newsize=(new_w, new_h))
                
                # Create branding background
                bg_img = Image.new("RGBA", (tgt_w, tgt_h), scene.backgroundColor or template.surfaceColor)
                bg_np = np.array(bg_img.convert("RGB"))
                bg_clip = ImageClip(bg_np).set_duration(scene_duration)
                
                # Composite centered
                video_centered = resized_vid.set_position("center").set_duration(scene_duration)
                
                # Create composition
                composite_layers = [bg_clip, video_centered]
                
                # If there's a caption, draw on transparent frame and overlay
                if scene.caption:
                    caption_overlay = Image.new("RGBA", (tgt_w, tgt_h), (0, 0, 0, 0))
                    caption_overlay = draw_caption_on_image(caption_overlay, scene.caption, caption_font, template)
                    
                    cap_np = np.array(caption_overlay)
                    cap_rgb = cap_np[:, :, :3]
                    cap_mask = cap_np[:, :, 3] / 255.0
                    
                    cap_clip = ImageClip(cap_rgb).set_ismask(False)
                    mask_clip = ImageClip(cap_mask, ismask=True)
                    cap_clip = cap_clip.set_mask(mask_clip).set_duration(scene_duration).set_position("center")
                    
                    composite_layers.append(cap_clip)
                    
                clip = CompositeVideoClip(composite_layers, size=template.resolution)
                # Mute the original recording audio to prioritize voiceover
                clip = clip.set_audio(None)
                
            else:
                console.print(f"[yellow]Warning: unknown scene type '{scene.type}'. Skipping.[/yellow]")
                progress.advance(scene_task)
                continue
                
            # Attach audio track
            if audio_clip:
                # If audio is longer than clip, stretch visual clip or let audio play
                # (For chat/title/outro we already set duration = max(dur, audio_dur))
                # For video scenes, we play voiceover over the video (if video is longer, play audio and then silence)
                if audio_clip.duration < clip.duration:
                    # Pad audio with silence
                    # In MoviePy, composite audio or simple set_audio works
                    clip = clip.set_audio(audio_clip)
                else:
                    clip = clip.set_audio(audio_clip.set_duration(clip.duration))
            
            clips.append(clip)
            progress.advance(scene_task)
            
        # 4. Concatenation and rendering
        progress.update(scene_task, description="[bold green]Concatenating scenes...")
        final_video = concatenate_videoclips(clips, method="compose")
        
        progress.update(scene_task, description="[bold yellow]Rendering final video...")
        
        # Render settings
        # We specify pixel format yuv420p for standard Reels/Instagram/Shorts compatibility
        # movflags +faststart allows streaming/instant start
        final_video.write_videofile(
            str(output_file),
            fps=template.fps,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(Path(cache_dir).parent / "temp-audio.m4a"),
            remove_temp=True,
            ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        )
        
    console.print("\n[bold green]Success! Video generated:[/bold green]")
    console.print(f"  [underline]{output_file}[/underline]")


@app.command()
def validate(
    input_path: str = typer.Option("examples/scripts/chat-only.json", "--input", "-i", help="Path to a JSON video script."),
) -> None:
    """Validate a script and its referenced template without rendering video."""
    input_file = resolve_path(input_path)
    if not input_file.exists():
        console.print(f"[red]Error: script file '{input_path}' was not found.[/red]")
        raise typer.Exit(1)

    try:
        with open(str(input_file), encoding="utf-8") as f:
            script_data = json.load(f)
        config = VideoConfig(**script_data)
    except Exception as e:
        console.print(f"[red]Script validation error: {e}[/red]")
        raise typer.Exit(1) from e

    template_file = resolve_path(config.template, base_dir=input_file.parent)
    if not template_file.exists():
        console.print(f"[red]Error: template file '{config.template}' was not found.[/red]")
        raise typer.Exit(1)

    try:
        with open(str(template_file), encoding="utf-8") as f:
            template_data = json.load(f)
        TemplateConfig(**template_data)
    except Exception as e:
        console.print(f"[red]Template validation error: {e}[/red]")
        raise typer.Exit(1) from e

    for scene in config.scenes:
        if scene.type == "video":
            if not scene.src:
                console.print("[red]Error: video scenes require a src field.[/red]")
                raise typer.Exit(1)
            video_src = resolve_path(scene.src, base_dir=input_file.parent)
            if not video_src.exists():
                console.print(f"[red]Error: video file '{scene.src}' was not found.[/red]")
                raise typer.Exit(1)

    console.print("[bold green]Script is valid.[/bold green]")


if __name__ == "__main__":
    app()
