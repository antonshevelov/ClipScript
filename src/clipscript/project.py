"""Project file loading, schema migration, and portable path resolution."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from clipscript.models import ScriptConfig, TemplateConfig

PACKAGE_DIR = Path(__file__).parent.resolve()


class ProjectError(ValueError):
    """A user-facing project file or path error."""


def resolve_path(path: str, base_dir: Path | None = None) -> Path:
    """Resolve absolute, scenario-relative, cwd-relative, and package-relative paths."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    bases = ([base_dir] if base_dir is not None else []) + [Path.cwd(), PACKAGE_DIR]
    candidates = [base / candidate for base in bases]
    for resolved in candidates:
        if resolved.exists() or resolved.parent.exists():
            return resolved
    return candidates[0]


def _copy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items()}


def normalize_script(data: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate the legacy root ``voiceover`` array into Schema v1 scenes."""
    normalized = _copy_mapping(data)
    if "schemaVersion" in normalized:
        return normalized

    voiceover = normalized.pop("voiceover", None)
    scenes = normalized.get("scenes")
    if not isinstance(voiceover, list) or not isinstance(scenes, list):
        raise ProjectError(
            "legacy scripts must include a root voiceover array and a scenes array"
        )
    if len(voiceover) != len(scenes):
        raise ProjectError(
            "legacy voiceover length must match the number of scenes"
        )

    migrated_scenes: list[dict[str, Any]] = []
    for scene, text in zip(scenes, voiceover):
        if not isinstance(scene, Mapping):
            raise ProjectError("legacy scenes must be objects")
        if not isinstance(text, str) or not text.strip():
            raise ProjectError("legacy voiceover entries must be non-empty strings")
        migrated = _copy_mapping(scene)
        migrated["voiceover"] = text
        migrated_scenes.append(migrated)

    normalized["schemaVersion"] = 1
    normalized["scenes"] = migrated_scenes
    return normalized


def parse_script(data: Mapping[str, Any]) -> ScriptConfig:
    """Normalize a script and validate it against the current strict schema."""
    try:
        return ScriptConfig.model_validate(normalize_script(data))
    except (ProjectError, ValidationError) as exc:
        raise ProjectError(str(exc)) from exc


def load_json(path: Path) -> Mapping[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectError(f"could not read JSON file '{path}': {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise ProjectError(f"JSON file '{path}' must contain an object")
    return loaded


@dataclass(frozen=True)
class Project:
    script_path: Path
    template_path: Path
    script: ScriptConfig
    template: TemplateConfig

    @property
    def script_dir(self) -> Path:
        return self.script_path.parent

    @property
    def template_dir(self) -> Path:
        return self.template_path.parent


def load_project(input_path: str) -> Project:
    script_path = resolve_path(input_path)
    if not script_path.is_file():
        raise ProjectError(f"script file '{input_path}' was not found")

    script = parse_script(load_json(script_path))
    template_path = resolve_path(script.template, base_dir=script_path.parent)
    if not template_path.is_file():
        raise ProjectError(f"template file '{script.template}' was not found")

    try:
        template = TemplateConfig.model_validate(load_json(template_path))
    except ValidationError as exc:
        raise ProjectError(str(exc)) from exc
    return Project(script_path, template_path, script, template)
