from pathlib import Path

import pytest

from clipscript.cli import Scene, TemplateConfig, VideoConfig, resolve_path


def test_template_defaults_to_edge_provider() -> None:
    template = TemplateConfig()

    assert template.ttsProvider == "edge"
    assert template.elevenlabsModelId == "eleven_multilingual_v2"


def test_invalid_scene_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid scene type"):
        Scene(type="unknown")


def test_voiceover_count_must_match_scenes() -> None:
    with pytest.raises(ValueError, match="Number of voiceover entries"):
        VideoConfig(
            title="bad",
            output="output/bad.mp4",
            template="templates/default.json",
            voiceover=["one"],
            scenes=[Scene(type="title"), Scene(type="outro")],
        )


def test_resolve_path_prefers_base_dir(tmp_path: Path) -> None:
    base = tmp_path / "scripts"
    base.mkdir()
    target = base / "demo.json"
    target.write_text("{}", encoding="utf-8")

    assert resolve_path("demo.json", base_dir=base) == target
