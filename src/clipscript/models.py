"""Strict Schema v2 models for ClipScript projects."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

PositiveSeconds = Annotated[float, Field(gt=0.0)]
NonNegativeSeconds = Annotated[float, Field(ge=0.0)]
PositiveInt = Annotated[int, Field(gt=0)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
SafeVolume = Annotated[float, Field(ge=0.0, le=2.0)]


class StrictModel(BaseModel):
    """Base model that rejects unknown fields and implicit coercion."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)


class TransitionConfig(StrictModel):
    """Transition entering this scene; a fade overlaps the preceding scene."""

    type: Literal["cut", "fade"] = "cut"
    duration: PositiveSeconds | None = None

    @model_validator(mode="after")
    def validate_duration(self) -> TransitionConfig:
        if self.type == "cut" and self.duration is not None:
            raise ValueError("cut transitions must not specify duration")
        if self.type == "fade" and self.duration is None:
            raise ValueError("fade transitions require duration")
        return self


class ChatMessage(StrictModel):
    text: Annotated[str, Field(min_length=1)]
    side: Literal["left", "right", "auto"] = "auto"
    author: Annotated[str, Field(min_length=1)] | None = None
    at: NonNegativeSeconds | None = None
    pause: NonNegativeSeconds = 0.0
    typing: PositiveSeconds | None = None

    @field_validator("text", "author")
    @classmethod
    def text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("text must not be blank")
        return value


class SceneBase(StrictModel):
    type: str
    voiceover: Annotated[str, Field(min_length=1)] | None = None
    voiceoverVolume: SafeVolume = 1.0
    subtitle: Annotated[str, Field(min_length=1)] | None = None
    transition: TransitionConfig = Field(default_factory=TransitionConfig)

    @field_validator("voiceover", "subtitle")
    @classmethod
    def narration_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("voiceover and subtitle must not be blank")
        return value


class ChatScene(SceneBase):
    type: Literal["chat"]
    duration: PositiveSeconds | None = None
    messages: list[Annotated[str, Field(min_length=1)] | ChatMessage] | None = None
    caption: Annotated[str, Field(min_length=1)] | None = None
    chatHeader: bool = True
    chatTitle: Annotated[str, Field(min_length=1)] = "Shared list"
    chatSubtitle: Annotated[str, Field(min_length=1)] = "Two participants"
    senderNames: bool = True
    participantCount: Literal[2, 3] = 3


class TitleScene(SceneBase):
    type: Literal["title"]
    duration: PositiveSeconds | None = None
    caption: Annotated[str, Field(min_length=1)] | None = None


class VideoScene(SceneBase):
    type: Literal["video"]
    src: Annotated[str, Field(min_length=1)]
    duration: PositiveSeconds | None = None
    start: NonNegativeSeconds = 0.0
    end: PositiveSeconds | None = None
    crop: list[int] | None = None
    backgroundColor: Color | None = None
    caption: Annotated[str, Field(min_length=1)] | None = None
    sourceAudioVolume: SafeVolume = 0.0

    @field_validator("crop")
    @classmethod
    def validate_crop(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if len(value) != 4:
            raise ValueError("crop must contain [x1, y1, x2, y2]")
        x1, y1, x2, y2 = value
        if min(value) < 0 or x2 <= x1 or y2 <= y1:
            raise ValueError("crop must be non-negative with x2 > x1 and y2 > y1")
        return value

    @model_validator(mode="after")
    def validate_trim(self) -> VideoScene:
        if self.duration is not None and self.end is not None:
            raise ValueError("video scenes must use duration or end, not both")
        if self.end is not None and self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class ImageScene(SceneBase):
    type: Literal["image"]
    src: Annotated[str, Field(min_length=1)]
    duration: PositiveSeconds | None = None
    fit: Literal["contain", "cover"] = "cover"
    backgroundColor: Color | None = None
    caption: Annotated[str, Field(min_length=1)] | None = None
    scale: Annotated[float, Field(gt=0.0, le=2.0)] = 1.0


class OutroScene(SceneBase):
    type: Literal["outro"]
    duration: PositiveSeconds | None = None
    caption: Annotated[str, Field(min_length=1)] | None = None
    url: Annotated[str, Field(min_length=1)] | None = None


Scene = Annotated[
    Union[ChatScene, TitleScene, VideoScene, ImageScene, OutroScene], Field(discriminator="type")
]


class SubtitleConfig(StrictModel):
    mode: Literal["off", "burn", "srt", "both"] = "off"
    output: Annotated[str, Field(min_length=1)] | None = None

    @field_validator("output")
    @classmethod
    def srt_extension(cls, value: str | None) -> str | None:
        if value is not None and not value.lower().endswith(".srt"):
            raise ValueError("subtitle output must use the .srt extension")
        return value


class ScriptConfig(StrictModel):
    schema_version: Literal[2] = Field(alias="schemaVersion")
    title: Annotated[str, Field(min_length=1)]
    output: Annotated[str, Field(min_length=1)]
    template: Annotated[str, Field(min_length=1)]
    scenes: list[Scene] = Field(min_length=1)
    subtitles: SubtitleConfig = Field(default_factory=SubtitleConfig)

    @model_validator(mode="after")
    def validate_scene_requirements(self, info: ValidationInfo) -> ScriptConfig:
        """Validate v2 while retaining v0/v1 timing semantics after migration."""
        compatibility = bool(info.context and info.context.get("compatibility"))
        if not self.output.lower().endswith(".mp4"):
            raise ValueError("output file must use the .mp4 extension")
        for index, scene in enumerate(self.scenes):
            if index == 0 and scene.transition.type != "cut":
                raise ValueError("the first scene must use a cut transition")
            if not compatibility:
                if isinstance(scene, ChatScene) and (scene.duration is None or not scene.messages):
                    raise ValueError("v2 chat scenes require duration and at least one message")
                if isinstance(scene, (TitleScene, OutroScene)) and (
                    scene.duration is None or scene.caption is None
                ):
                    raise ValueError(f"v2 {scene.type} scenes require duration and caption")
                if isinstance(scene, (VideoScene, ImageScene)) and scene.duration is None:
                    raise ValueError(f"v2 {scene.type} scenes require duration")
                if isinstance(scene, ChatScene) and scene.messages and any(
                    isinstance(message, str) for message in scene.messages
                ):
                    raise ValueError("v2 chat messages must be structured objects")
            if isinstance(scene, ChatScene) and scene.messages and scene.duration is not None:
                explicit = [
                    message.at
                    for message in scene.messages
                    if isinstance(message, ChatMessage) and message.at is not None
                ]
                if explicit != sorted(explicit):
                    raise ValueError("chat message at values must be monotonic")
                # Local import avoids a model/timeline import cycle while validating resolved timing.
                from clipscript.timeline import validate_chat_timeline

                validate_chat_timeline(scene, scene.duration)
            if index > 0 and scene.transition.type == "fade":
                previous = self.scenes[index - 1]
                duration = scene.transition.duration
                if duration is not None and (
                    (previous.duration is not None and duration > previous.duration)
                    or (scene.duration is not None and duration > scene.duration)
                ):
                    raise ValueError("fade transition duration must not exceed adjacent scene durations")
        return self


class TemplateConfig(StrictModel):
    resolution: list[PositiveInt] = Field(default_factory=lambda: [1080, 1920])
    fps: PositiveInt = 30
    brandColor: Color = "#0f7b6c"
    surfaceColor: Color = "#fdf9f1"
    textColor: Color = "#17211f"
    accentColor: Color = "#43a047"
    logo: str | None = None
    voice: Annotated[str, Field(min_length=1)] = "uk-UA-PolinaNeural"
    voice_id: str | None = None
    elevenlabsModelId: Annotated[str, Field(min_length=1)] = "eleven_multilingual_v2"
    fontFamily: Annotated[str, Field(min_length=1)] = "system"
    ttsProvider: Literal["edge", "elevenlabs"] = "edge"

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, value: list[int]) -> list[int]:
        if len(value) != 2:
            raise ValueError("resolution must contain [width, height]")
        if value[0] > 8192 or value[1] > 8192:
            raise ValueError("resolution dimensions must not exceed 8192")
        return value

    @field_validator("fps")
    @classmethod
    def validate_fps(cls, value: int) -> int:
        if value > 120:
            raise ValueError("fps must not exceed 120")
        return value
