from __future__ import annotations

from pathlib import Path


def test_macos_python39_urllib3_compatibility_marker_is_scoped() -> None:
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")

    assert "urllib3>=1.26.20,<2; sys_platform == 'darwin' and python_version < '3.10'" in pyproject
