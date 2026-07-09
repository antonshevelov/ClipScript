# Script Format

ClipScript videos are JSON documents validated against strict Schema v2.

## Root Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `schemaVersion` | `2` | yes | Current script schema version. |
| `title` | string | yes | Internal video name. |
| `output` | string | yes | MP4 output path, relative to the script file. |
| `template` | string | yes | Template path, relative to the script file. |
| `scenes` | object[] | yes | Ordered scene definitions. |
| `subtitles` | object | no | `off` (default), `burn`, `srt`, or `both`; SRT is next to MP4 unless `output` is set relative to the script. |

Each scene can include optional non-empty `voiceover`, `subtitle`, `voiceoverVolume` (0-2), and a `transition` entering that scene. A fade overlaps the preceding scene and may not exceed either adjacent duration. Scenes without voiceover do not call TTS. Unknown fields and coercion are rejected.

## Paths

Script `output`, `template`, and video `src` paths resolve relative to the script file. Template `logo` resolves relative to the template file.

## Scene: `chat`

```json
{
  "type": "chat",
  "duration": 8,
  "voiceover": "Optional narration for this scene",
  "chatHeader": false,
  "chatTitle": "Shared list",
  "chatSubtitle": "Two participants",
  "senderNames": false,
  "participantCount": 2,
  "messages": [
    {"text": "Message 1", "author": "Marta", "at": 0.5, "typing": 0.3, "pause": 0.4},
    {"text": "Message 2", "author": "You", "side": "right"}
  ]
}
```

In Schema v2, `duration` and a non-empty structured `messages` list are required. A message has `text`, optional `side` (`left`, `right`, `auto`), `author`, absolute `at`, `pause`, and positive `typing`; the resolved appearance and pause schedule must fit within the scene. `pause` begins after a message appears and delays the next implicit message: in this example the first message appears at `0.5`, then its `0.4` pause places the second message at `0.9`. Appearance must be strictly before the scene duration. When `senderNames` is true, an explicit or automatic author label is shown above either side's bubble and aligned to that bubble. A fade is configured as `{"type":"fade","duration":0.4}` on the scene it enters.

The generated JSON Schema retains a legacy string-message branch because the same runtime model automatically loads Schema v1 scripts. New Schema v2 source files must use structured message objects; string messages are rejected during v2 validation.

## Scene: `title`

```json
{
  "type": "title",
  "duration": 1.5,
  "caption": "Sound familiar?",
  "voiceover": "Sound familiar?"
}
```

In Schema v2, `duration` and `caption` are required.

## Scene: `video`

```json
{
  "type": "video",
  "src": "../assets/app-demo.mp4",
  "start": 0,
  "duration": 10,
  "crop": [100, 0, 984, 1920],
  "backgroundColor": "#f9fcf9",
  "caption": "Use a real screen recording"
}
```

In Schema v2, `src` and `duration` are required. `start` defaults to `0`; `end` may be used for compatibility but cannot be combined with duration. `sourceAudioVolume` defaults to `0`, preserving v0.1.1 mute behavior; positive values preserve and mix original audio with voiceover.

## Scene: `image`

```json
{"type":"image","src":"../assets/photo.png","duration":2,"fit":"contain","backgroundColor":"#ffffff"}
```

Images resolve relative to the script. `duration` is required; `fit` is `contain` or `cover`; corrupt or unsupported files fail validation/rendering with a user-facing error.

## Scene: `outro`

```json
{
  "type": "outro",
  "duration": 3,
  "caption": "Make short demos from scripts",
  "url": "https://example.com"
}
```

In Schema v2, `duration` and `caption` are required. `url` is optional.

## Legacy 0.1.0 Scripts

Unversioned scripts remain accepted when they include the legacy root `voiceover` array. Schema v1 is also accepted. Both normalize to Schema v2 at runtime without user edits.

Legacy scenes may omit timing. Chat, title, and outro then use their voiceover duration, or a 5-second fallback. Video scenes without `duration` or `end` likewise use voiceover duration or 5 seconds, clamped to the source media.

`examples/scripts/legacy-v0.json` is a runnable validation fixture for this compatibility path.

When `schemaVersion: 1` is present, root `voiceover` is forbidden. This is a format-level breaking change for new versioned scripts only. Existing scene types and both TTS providers are retained.
