"""Deterministic planning for chat-message appearance and typing states."""

from __future__ import annotations

from dataclasses import dataclass

from clipscript.models import ChatScene


@dataclass(frozen=True)
class PlannedMessage:
    text: str
    side: str
    sender: str | None
    appears_at: float
    typing_from: float | None

    def is_visible(self, timestamp: float) -> bool:
        return timestamp >= self.appears_at

    def is_typing(self, timestamp: float) -> bool:
        return self.typing_from is not None and self.typing_from <= timestamp < self.appears_at


def _legacy_times(count: int, duration: float) -> list[float]:
    start = min(0.2, duration / 4)
    end = max(start, duration - min(1.2, duration / 4))
    step = (end - start) / max(count - 1, 1)
    return [start + index * step for index in range(count)]


def plan_chat_timeline(scene: ChatScene, duration: float) -> list[PlannedMessage]:
    """Plan visible text without depending on Pillow or MoviePy frame rendering."""
    messages = scene.messages or []
    if not messages:
        return []
    if all(isinstance(message, str) for message in messages):
        return [
            PlannedMessage(text=message, side="auto", sender=None, appears_at=at, typing_from=None)
            for message, at in zip(messages, _legacy_times(len(messages), duration))
            if isinstance(message, str)
        ]

    planned: list[PlannedMessage] = []
    cursor = min(0.2, duration / 4)
    for message in messages:
        if isinstance(message, str):
            raise ValueError("mixed legacy and structured chat messages are not supported")
        typing = message.typing or 0.0
        appears_at = message.at if message.at is not None else cursor + typing
        planned.append(
            PlannedMessage(
                text=message.text,
                side=message.side,
                sender=message.sender,
                appears_at=appears_at,
                typing_from=appears_at - typing if typing else None,
            )
        )
        cursor = appears_at + message.pause
    return planned


def validate_chat_timeline(scene: ChatScene, duration: float) -> None:
    """Reject timing combinations that cannot be displayed within the scene."""
    planned = plan_chat_timeline(scene, duration)
    for index, message in enumerate(planned):
        if message.typing_from is not None and message.typing_from < 0:
            raise ValueError("chat message typing cannot begin before scene start")
        if message.appears_at > duration:
            raise ValueError("chat message appearance must be within scene duration")
        source = scene.messages[index] if scene.messages is not None else None
        pause = source.pause if not isinstance(source, str) and source is not None else 0.0
        if message.appears_at + pause > duration:
            raise ValueError("chat message pause extends beyond scene duration")
        if index:
            previous = planned[index - 1]
            previous_source = scene.messages[index - 1] if scene.messages is not None else None
            previous_pause = (
                previous_source.pause
                if not isinstance(previous_source, str) and previous_source is not None
                else 0.0
            )
            if message.appears_at < previous.appears_at + previous_pause:
                raise ValueError("chat message timing conflicts with previous pause")


def resolved_side(index: int, requested: str) -> str:
    """Retain the legacy alternating-side behaviour for ``auto`` messages."""
    return requested if requested != "auto" else ("left" if index % 2 == 0 else "right")
