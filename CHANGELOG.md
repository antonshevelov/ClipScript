# Changelog

## [0.2.0]

- Added Schema v2, timed structured chat messages, image scenes, fade transitions, subtitles, and source/voiceover audio mixing.
- Added `init`, `doctor`, `preview`, `schema`, `voices`, and `cache clear` commands.
- Preserved automatic migration and rendering compatibility for v0.1.0 and Schema v1 scripts.

## 0.1.1

- Stabilized the renderer around a versioned strict Schema v1.
- Moved voiceover from the root array to an optional `voiceover` field on each scene.
- Preserved compatibility with unversioned 0.1.0 scripts by migrating their root voiceover array at load time.
- Migrated media handling to MoviePy 2.x and added deterministic resource cleanup.
- Added provider and renderer registries, atomic SHA-256 TTS caching, offline render coverage, and CI checks.
- The alpha Python module API moved from `clipscript.cli` to dedicated modules; imports from the old monolith are not preserved as a compatibility contract.
- Renderer and TTS registries are internal Python dependency-injection points, not a JSON plugin API.
- Pinned the strict typecheck toolchain to mypy 1.x for reproducible Python 3.9-3.12 CI.

### Compatibility

- Existing unversioned 0.1.0 scripts remain accepted without changes.
- Schema v1 rejects the former root `voiceover` field. This is a format-level breaking change only for newly versioned scripts.

## 0.1.0

- Initial open-source extraction.
- JSON-driven scene rendering.
- Chat, title, video, and outro scenes.
- Edge TTS and ElevenLabs TTS providers.
- Scenario-relative path resolution.
- Example scripts and templates.
