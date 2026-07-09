"""Strict, versioned data models for ClipScript scripts and templates."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PositiveSeconds = Annotated[float, Field(gt=0.0)]
NonNegativeSeconds = Annotated[float, Field(ge=0.0)]
PositiveInt = Annotated[int, Field(gt=0)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


class StrictModel(BaseModel):
    """Base model that rejects unknown fields and coercion-prone input."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)


class SceneBase(StrictModel):
    type: str
    voiceover: str | None = None

    @field_validator("voiceover")
    @classmethod
    def voiceover_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("voiceover must not be blank")
        return value


class ChatScene(SceneBase):
    type: Literal["chat"]
    duration: PositiveSeconds
    messages: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    caption: str | None = None
    chatHeader: bool = True
    chatTitle: Annotated[str, Field(min_length=1)] = "Shared list"
    chatSubtitle: Annotated[str, Field(min_length=1)] = "Two participants"
    senderNames: bool = True
    participantCount: Literal[2, 3] = 3


class TitleScene(SceneBase):
    type: Literal["title"]
    duration: PositiveSeconds
    caption: Annotated[str, Field(min_length=1)]


class VideoScene(SceneBase):
    type: Literal["video"]
    src: Annotated[str, Field(min_length=1)]
    duration: PositiveSeconds | None = None
    start: NonNegativeSeconds = 0.0
    end: PositiveSeconds | None = None
    crop: list[int] | None = None
    backgroundColor: Color | None = None
    caption: str | None = None

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
        if self.duration is None and self.end is None:
            raise ValueError("video scenes require duration or end")
        if self.duration is not None and self.end is not None:
            raise ValueError("video scenes must use duration or end, not both")
        if self.end is not None and self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class OutroScene(SceneBase):
    type: Literal["outro"]
    duration: PositiveSeconds
    caption: Annotated[str, Field(min_length=1)]
    url: Annotated[str, Field(min_length=1)] | None = None


Scene = Annotated[
    Union[ChatScene, TitleScene, VideoScene, OutroScene], Field(discriminator="type")
]


class ScriptConfig(StrictModel):
    schema_version: Literal[1] = Field(alias="schemaVersion")
    title: Annotated[str, Field(min_length=1)]
    output: Annotated[str, Field(min_length=1)]
    template: Annotated[str, Field(min_length=1)]
    scenes: list[Scene] = Field(min_length=1)


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
