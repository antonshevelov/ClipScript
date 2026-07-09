from __future__ import annotations

from pathlib import Path

import pytest

from clipscript.models import TemplateConfig
from clipscript.project import ProjectError, load_project, parse_script, resolve_path


def script_data() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "title": "Demo",
        "output": "output/demo.mp4",
        "template": "template.json",
        "scenes": [{"type": "title", "duration": 1.0, "caption": "Hello"}],
    }


def test_strict_schema_rejects_unknown_and_wrong_scene_fields() -> None:
    data = script_data()
    data["unknown"] = True
    with pytest.raises(ProjectError, match="unknown"):
        parse_script(data)

    data = script_data()
    data["scenes"] = [{"type": "title", "duration": 1.0, "caption": "Hello", "messages": []}]
    with pytest.raises(ProjectError, match="messages"):
        parse_script(data)


@pytest.mark.parametrize(
    ("scene", "message"),
    [
        ({"type": "chat", "duration": 1.0, "messages": []}, "at least 1"),
        ({"type": "video", "src": "video.mp4"}, "duration or end"),
        ({"type": "video", "src": "video.mp4", "duration": 1.0, "end": 1.0}, "not both"),
        ({"type": "video", "src": "video.mp4", "end": 1.0, "crop": [0, 0, 0, 1]}, "crop"),
        ({"type": "outro", "duration": 0.0, "caption": "Bye"}, "greater than 0"),
    ],
)
def test_scene_constraints_are_enforced(scene: dict[str, object], message: str) -> None:
    data = script_data()
    data["scenes"] = [scene]
    with pytest.raises(ProjectError, match=message):
        parse_script(data)


def test_legacy_root_voiceover_is_migrated() -> None:
    legacy = {
        "title": "Legacy",
        "output": "output/legacy.mp4",
        "template": "template.json",
        "voiceover": ["First", "Second"],
        "scenes": [
            {"type": "title", "duration": 1.0, "caption": "First"},
            {"type": "outro", "duration": 1.0, "caption": "Second"},
        ],
    }

    config = parse_script(legacy)

    assert config.schema_version == 1
    assert config.scenes[0].voiceover == "First"
    assert config.scenes[1].voiceover == "Second"


def test_legacy_example_file_is_valid_and_migrated() -> None:
    repository_root = Path(__file__).resolve().parents[1]

    project = load_project(str(repository_root / "examples" / "scripts" / "legacy-v0.json"))

    assert project.script.schema_version == 1
    assert project.script.scenes[0].voiceover is not None


def test_versioned_script_rejects_legacy_root_voiceover() -> None:
    data = script_data()
    data["voiceover"] = ["No longer valid here"]
    with pytest.raises(ProjectError, match="voiceover"):
        parse_script(data)


def test_template_rejects_invalid_resolution_and_fps() -> None:
    with pytest.raises(ValueError, match="resolution"):
        TemplateConfig(resolution=[1080])
    with pytest.raises(ValueError, match="fps"):
        TemplateConfig(fps=121)
    # Runtime schema must reject values that static typing prevents in normal callers.
    with pytest.raises(ValueError):
        TemplateConfig(fps="30")  # type: ignore[arg-type]


def test_schema_rejects_numeric_strings() -> None:
    data = script_data()
    data["scenes"] = [{"type": "title", "duration": "1.0", "caption": "Hello"}]
    with pytest.raises(ProjectError, match="duration"):
        parse_script(data)


def test_resolve_path_prefers_script_directory(tmp_path: Path) -> None:
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    target = script_dir / "template.json"
    target.write_text("{}", encoding="utf-8")

    assert resolve_path("template.json", base_dir=script_dir) == target
